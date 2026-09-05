"""FastAPI app — "bang mach": tao app, gan CORS + exception handler, include router.

Khong nghiep vu o day. /docs (Swagger) + /openapi.json bat mac dinh — la "hop dong"
API cho FE (origin R9).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import health, majors, program_detail, school_detail, schools
from app.config import settings

logger = logging.getLogger("hocphi")

app = FastAPI(
    title="hocphi.info API",
    version="0.4.0",
    description=(
        "Tra cuu & so sanh hoc phi dai hoc Viet Nam. "
        "GET /api/majors (?search=), /api/schools (?search=), "
        "/api/schools/{school_slug}/majors/{major_slug}, "
        "/api/schools/{school_slug}."
    ),
)

# CORS — cho phep origin FE goi cheo (origin R10). Danh sach qua bien moi truong.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Moi loi chua bat -> JSON co cau truc, khong lo stack (origin R11).

    Structured logging day du la Tuan 5 — Tuan 1 chi logger.exception.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(majors.router)
app.include_router(schools.router)
app.include_router(program_detail.router)
app.include_router(school_detail.router)
