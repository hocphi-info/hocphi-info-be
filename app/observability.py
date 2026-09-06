"""Request-id + structured logging (Tuần 5).

Bốn mảnh, cố ý gom một file vì chúng dùng chung nhau:

- `request_id_ctx` — `ContextVar` giữ id của request đang chạy. `ContextVar` là
  biến "theo ngữ cảnh chạy": mỗi request chạy trong một `asyncio.Task` riêng với
  một bản sao context riêng, nên set ở đây không rò sang request khác. Tương
  đương `Zone`/`Zone.current` bên Dart, hoặc thread-local nhưng đúng cho async.
- `configure_logging()` — dựng structlog: mọi log ra **một dòng JSON / bản ghi**
  (hoặc màu, dễ đọc khi `LOG_FORMAT=console`), tự đính `request_id` nhờ
  `merge_contextvars`. Gọi **một lần** lúc khởi động, trước khi tạo `FastAPI()`.
- `RequestContextMiddleware` — ASGI middleware thuần (KHÔNG `BaseHTTPMiddleware`:
  cái đó chạy endpoint trong task con nên `ContextVar` set trong nó không
  propagate xuống endpoint). Mỗi request: lấy/validate `X-Request-ID` gửi vào
  hoặc sinh mới, bind vào context, chèn lại vào response header, và ghi đúng
  MỘT dòng access log lúc xong (kèm `query_count`/`query_ms` gom từ mảnh dưới).
- `configure_sql_logging(engine)` — gắn event `before/after_cursor_execute` của
  SQLAlchemy để (a) đếm số query + thời gian SQL mỗi request vào `sql_stats_ctx`
  (luôn bật), (b) khi `SQL_LOG=true` thì ghi thêm một dòng `event="sql"` / câu
  lệnh. Gọi **một lần** lúc khởi động, sau khi tạo engine.

Rate-limit: xem TODO ở `RequestContextMiddleware` — hoãn tới khi có traffic.
"""

import logging
import re
import sys
from contextvars import ContextVar
from time import perf_counter
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

# ── request-id context ───────────────────────────────────────────────────────
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Bộ đếm SQL theo request. `RequestContextMiddleware` set một dict mới ở đầu mỗi
# request, các event listener của SQLAlchemy (xem `configure_sql_logging`) cộng
# dồn vào đó, dòng access log đọc lại lúc kết thúc. `None` = đang chạy ngoài một
# request (script seed, health check trong task nền…) → listener bỏ qua, không đếm.
sql_stats_ctx: ContextVar[dict[str, float] | None] = ContextVar(
    "sql_stats", default=None
)

# `X-Request-ID` từ ngoài có thể do CDN/proxy đặt — nhận lại để nối được trace,
# nhưng chỉ khi "lành": chữ-số-gạch, tối đa 128 ký tự. Không hợp lệ → sinh mới.
_REQUEST_ID_RE = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")

# Các path không sinh dòng access log — healthcheck của compose gọi /health mỗi
# 5s, /docs và /openapi.json là tài nguyên tĩnh. Bỏ để log còn tín hiệu.
_QUIET_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


def get_request_id() -> str | None:
    """Id của request đang xử lý (exception handler / code khác đọc để log)."""
    return request_id_ctx.get()


# ── structlog config ─────────────────────────────────────────────────────────
_configured = False

# Processor dùng chung cho cả bản ghi structlog lẫn bản ghi stdlib logging
# (uvicorn) — nhờ vậy log của thư viện bên thứ ba cũng cùng một hình dạng.
_SHARED_PROCESSORS: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging() -> None:
    """Dựng structlog + đưa log stdlib (uvicorn) qua cùng pipeline. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.log_format == "console"
        else structlog.processors.JSONRenderer()
    )

    # structlog phía "trước": chạy shared processor rồi bàn giao cho formatter
    # của stdlib logging (để một chỗ render duy nhất).
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # bản ghi đến từ stdlib logging (không qua structlog) vẫn được "làm giàu"
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # uvicorn.error → chảy qua root (JSON). uvicorn.access → tắt hẳn: dòng access
    # log của ta (trong middleware) thay thế, tránh log đôi.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True


_access_log = structlog.get_logger("hocphi.request")


# ── ASGI middleware ──────────────────────────────────────────────────────────
class RequestContextMiddleware:
    """Gán request-id cho mọi request; ghi một dòng access log lúc xong.

    TODO(rate-limit, hoãn — xem docs/brainstorms/2026-09-06-week5-observability-
    drop-redis-requirements.md §R6): chèn kiểm tra giới hạn theo IP tại đây
    (fixed-window hoặc token-bucket, dict in-process — 1 instance không cần store
    ngoài). Bật khi deploy hoặc khi thấy abuse.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = Headers(scope=scope).get("x-request-id")
        rid = inbound if inbound and _REQUEST_ID_RE.match(inbound) else uuid4().hex

        token = request_id_ctx.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        started = perf_counter()
        seen_status = 500
        sql_stats: dict[str, float] = {"count": 0, "time_ms": 0.0}
        sql_token = sql_stats_ctx.set(sql_stats)

        async def send_wrapper(message: Message) -> None:
            nonlocal seen_status
            if message["type"] == "http.response.start":
                seen_status = message["status"]
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        raised = False
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            raised = True
            raise
        finally:
            if scope["path"] not in _QUIET_PATHS:
                client = scope.get("client")
                # request_id cung nam trong contextvars (merge_contextvars gan vao
                # moi dong log cua request); ghi thang o day de dong access log tu du.
                _access_log.info(
                    "request",
                    request_id=rid,
                    method=scope["method"],
                    path=scope["path"],
                    status_code=500 if raised else seen_status,
                    duration_ms=round((perf_counter() - started) * 1000, 1),
                    client_ip=client[0] if client else None,
                    query_count=int(sql_stats["count"]),
                    query_ms=round(sql_stats["time_ms"], 1),
                )
            # Đường bình thường: dọn ngay. Đường lỗi: KHÔNG dọn — exception
            # handler (chạy sau, ngoài middleware này) còn cần đọc request_id để
            # đưa vào body/header; Task của request này sẽ bị server bỏ đi nên
            # không có rò rỉ sang request sau.
            if not raised:
                structlog.contextvars.clear_contextvars()
                request_id_ctx.reset(token)
                sql_stats_ctx.reset(sql_token)


# ── SQL logging ──────────────────────────────────────────────────────────────
_sql_log = structlog.get_logger("hocphi.sql")


def configure_sql_logging(sync_engine: Engine) -> None:
    """Gắn hai event vào `Engine` đồng bộ nằm dưới `AsyncEngine`.

    SQLAlchemy phát `before/after_cursor_execute` quanh MỖI câu lệnh gửi xuống
    driver. Ta dùng chúng cho hai việc:

    - **Luôn bật, gần như free:** cộng số query + tổng thời gian vào
      `sql_stats_ctx` của request đang chạy → `RequestContextMiddleware` in ra
      `query_count` / `query_ms` trong dòng access log.
    - **Chỉ khi `settings.sql_log`:** ghi thêm một dòng log `event="sql"` cho
      từng câu — statement (gộp về một dòng), tham số (cắt 500 ký tự), thời gian,
      số dòng. `merge_contextvars` tự đính `request_id` nên lọc theo id là ra
      đủ SQL của một request.

    Thời gian đo bằng một stack (`list`) trên `conn.info`: cùng một connection có
    thể chạy lồng nhau (câu này gọi ra câu khác) nên push lúc `before`, pop lúc
    `after` mới ghép đúng cặp. Gọi hàm này một lần lúc khởi động.
    """

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start_stack: list[float] = conn.info.setdefault("_q_start", [])
        start_stack.append(perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start_stack: list[float] = conn.info["_q_start"]
        elapsed_ms = (perf_counter() - start_stack.pop()) * 1000

        stats = sql_stats_ctx.get()
        if stats is not None:
            stats["count"] += 1
            stats["time_ms"] += elapsed_ms

        if settings.sql_log:
            _sql_log.info(
                "sql",
                # `merge_contextvars` cũng đính request_id, nhưng ghi thẳng như
                # dòng access log cho chắc (test / xử lý ngoài pipeline vẫn thấy).
                request_id=request_id_ctx.get(),
                statement=" ".join(statement.split()),  # gộp SQL nhiều dòng về 1
                params=repr(parameters)[:500],
                duration_ms=round(elapsed_ms, 2),
                rows=cursor.rowcount if cursor.rowcount != -1 else None,
            )
