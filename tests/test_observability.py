"""Tuần 5 — request-id middleware + structured logging.

Phần lớn test dựng một app FastAPI tí hon chỉ có `RequestContextMiddleware` +
vài route tầm thường (`/ping`, `/boom`, `/health`) — hành vi của middleware
không phụ thuộc router thật hay DB, tách ra vậy cho nhanh và khỏi giòn. Một test
riêng cuối cùng chạm `app` thật để chắc middleware đã được gắn.
"""

import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import structlog
from app.main import app, unhandled_exception_handler
from app.observability import RequestContextMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

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


# ── SQL logging (configure_sql_logging) ──────────────────────────────────────
# Không đi qua `app.db.engine` (pool tạo lúc import, dễ dính prepared-statement
# cũ sau khi test_migrations roundtrip schema). Mỗi test tự dựng 1 engine "một
# lần rồi bỏ" trỏ vào DB test, gắn listener, rồi cho mini-app chạy 1 câu SQL.


@pytest_asyncio.fixture
async def sql_engine() -> AsyncGenerator[AsyncEngine, None]:
    from app.config import settings
    from app.observability import configure_sql_logging

    eng = create_async_engine(settings.database_url)
    configure_sql_logging(eng.sync_engine)
    yield eng
    await eng.dispose()


def _mini_app_touching_db(eng: AsyncEngine) -> FastAPI:
    mini = _mini_app()

    @mini.get("/query")
    async def _query() -> dict[str, bool]:
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True}

    return mini


async def test_access_log_carries_sql_counters(sql_engine: AsyncEngine) -> None:
    """Dòng access log kèm `query_count` + `query_ms` cho mỗi request chạm DB."""
    with structlog.testing.capture_logs() as logs:
        async with _client(_mini_app_touching_db(sql_engine)) as client:
            resp = await client.get("/query")
    assert resp.status_code == 200

    line = next(e for e in logs if e["event"] == "request")
    assert line["query_count"] >= 1
    assert isinstance(line["query_ms"], float)
    assert line["query_ms"] >= 0


async def test_no_sql_counters_leak_outside_a_request(sql_engine: AsyncEngine) -> None:
    """`sql_stats_ctx` mặc định None → listener chạy ngoài request không nổ."""
    from app.observability import sql_stats_ctx

    assert sql_stats_ctx.get() is None
    async with sql_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))  # không được raise


async def test_sql_log_lines_only_when_enabled(
    sql_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SQL_LOG` tắt → không dòng `event="sql"`; bật → có, kèm đúng request_id."""
    from app import observability

    mini = _mini_app_touching_db(sql_engine)

    async with _client(mini) as client:
        with structlog.testing.capture_logs() as off_logs:
            await client.get("/query")
        assert [e for e in off_logs if e.get("event") == "sql"] == []

        monkeypatch.setattr(observability.settings, "sql_log", True)
        with structlog.testing.capture_logs() as on_logs:
            await client.get("/query", headers={"X-Request-ID": "trace-sql-1"})

    sql_lines = [e for e in on_logs if e.get("event") == "sql"]
    assert sql_lines
    assert all(e["request_id"] == "trace-sql-1" for e in sql_lines)
    assert any("SELECT" in e["statement"].upper() for e in sql_lines)
    assert all(isinstance(e["duration_ms"], float) for e in sql_lines)
