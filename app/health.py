"""GET /health — endpoint ngan nhat, chua du khung moi module Tuan 2+ se copy:
APIRouter + Depends(get_session) + chay 1 query + tra Pydantic response model.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    """Pydantic response model — FastAPI dung de validate + sinh OpenAPI schema."""

    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]


@router.get("/health", response_model=HealthOut)
async def health(
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> HealthOut:
    """Kiem tra API song + ket noi DB. DB chet -> 503 (khong de 500 lo stack)."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="degraded", db="down")
    return HealthOut(status="ok", db="ok")
