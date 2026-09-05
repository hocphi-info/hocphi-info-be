"""Tuần 5 — request-id middleware + structured logging.

Phần lớn test dựng một app FastAPI tí hon chỉ có `RequestContextMiddleware` +
vài route tầm thường (`/ping`, `/boom`, `/health`) — hành vi của middleware
không phụ thuộc router thật hay DB, tách ra vậy cho nhanh và khỏi giòn. Một test
riêng cuối cùng chạm `app` thật để chắc middleware đã được gắn.
"""

import re

import structlog
from app.main import app, unhandled_exception_handler
from app.observability import RequestContextMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_HEX32 = re.compile(r"\A[0-9a-f]{32}\Z")


def _client(target: FastAPI, *, raise_app_exceptions: bool = True) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=target, raise_app_exceptions=raise_app_exceptions),
        base_url="http://test",
    )


def _mini_app() -> FastAPI:
    """Cùng khung middleware + exception handler với app thật, không router/DB."""
    mini = FastAPI()
    mini.add_middleware(CORSMiddleware, allow_origins=["*"])
    mini.add_middleware(RequestContextMiddleware)
    mini.add_exception_handler(Exception, unhandled_exception_handler)

    @mini.get("/ping")
    async def _ping() -> dict[str, bool]:
        return {"ok": True}

    @mini.get("/health")  # path nằm trong _QUIET_PATHS
    async def _health() -> dict[str, bool]:
        return {"ok": True}

    @mini.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("kaboom")

    return mini


async def test_response_carries_generated_request_id_header() -> None:
    async with _client(_mini_app()) as client:
        resp = await client.get("/ping")
    assert resp.status_code == 200
    assert _HEX32.match(resp.headers["x-request-id"])


async def test_inbound_request_id_is_echoed_back() -> None:
    sent = "trace-abc_123"
    async with _client(_mini_app()) as client:
        resp = await client.get("/ping", headers={"X-Request-ID": sent})
    assert resp.headers["x-request-id"] == sent


async def test_invalid_inbound_request_id_is_replaced() -> None:
    for bad in ("has spaces", "x" * 200, "bad;semicolon", ""):
        async with _client(_mini_app()) as client:
            resp = await client.get("/ping", headers={"X-Request-ID": bad})
        got = resp.headers["x-request-id"]
        assert got != bad
        assert _HEX32.match(got)


async def test_unhandled_error_body_and_header_share_request_id() -> None:
    async with _client(_mini_app(), raise_app_exceptions=False) as client:
        resp = await client.get("/boom", headers={"X-Request-ID": "trace-boom-1"})
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error"
    assert body["requestId"] == "trace-boom-1"
    assert resp.headers["x-request-id"] == "trace-boom-1"


async def test_access_log_line_is_structured_with_request_id() -> None:
    with structlog.testing.capture_logs() as logs:
        async with _client(_mini_app()) as client:
            await client.get("/ping", headers={"X-Request-ID": "trace-log-1"})

    line = next(e for e in logs if e["event"] == "request")
    assert line["request_id"] == "trace-log-1"
    assert line["method"] == "GET"
    assert line["path"] == "/ping"
    assert line["status_code"] == 200
    assert isinstance(line["duration_ms"], float)
    assert line["client_ip"] == "127.0.0.1"


async def test_quiet_paths_get_header_but_no_access_log() -> None:
    with structlog.testing.capture_logs() as logs:
        async with _client(_mini_app()) as client:
            resp = await client.get("/health")

    assert _HEX32.match(resp.headers["x-request-id"])
    assert [e for e in logs if e.get("event") == "request"] == []


async def test_middleware_is_wired_into_the_real_app(db: AsyncSession) -> None:
    async with _client(app) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert _HEX32.match(resp.headers["x-request-id"])
