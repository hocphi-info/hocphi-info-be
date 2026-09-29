"""FastAPI app — "bang mach": tao app, gan CORS + exception handler, include router.

Khong nghiep vu o day. /docs (Swagger) + /openapi.json bat mac dinh — la "hop dong"
API cho FE (origin R9).
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import health
from app.config import settings
from app.db import engine
from app.observability import (
    RequestContextMiddleware,
    configure_logging,
    configure_sql_logging,
    get_request_id,
)
from app.v1 import (
    coverage,
    majors,
    program_detail,
    school_detail,
    schools,
    taxonomy,
)

# Dung structlog TRUOC khi tao app / bat ky log nao — mot lan / process.
configure_logging()
# Gan event dem/log SQL vao engine dong bo ben duoi AsyncEngine (mot lan / process).
configure_sql_logging(engine.sync_engine)

logger = structlog.get_logger("hocphi")

app = FastAPI(
    title="hocphi.info API",
    version="0.4.0",
    description=(
        "Tra cuu & so sanh hoc phi dai hoc Viet Nam. "
        "GET /api/v1/majors (?search=), /api/v1/schools (?search=), "
        "/api/v1/schools/{school_slug}/majors/{major_slug}, "
        "/api/v1/schools/{school_slug}, /api/v1/coverage, "
        "/api/v1/taxonomy[/{code}]."
    ),
)

# Thu tu: CORS o NGOAI (moi response, ke ca loi, phai co header CORS de browser
# doc duoc), RequestContext o TRONG. `add_middleware` boc tu ngoai vao nen add
# CORS truoc, RequestContext sau.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Moi loi chua bat -> JSON co cau truc, khong lo stack (origin R11).

    Kem `requestId` (tu contextvar cua RequestContextMiddleware) o body VA header
    de mot bao loi tu nguoi dung tra nguoc duoc ve dong log tuong ung.
    """
    request_id = get_request_id()
    logger.exception("unhandled_error", method=request.method, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "requestId": request_id},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


app.include_router(health.router)
app.include_router(majors.router)
app.include_router(schools.router)
app.include_router(program_detail.router)
app.include_router(school_detail.router)
app.include_router(coverage.router)
app.include_router(taxonomy.router)
