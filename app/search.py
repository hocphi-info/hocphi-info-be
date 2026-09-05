"""GET /api/search?q= (F13) — tim nhanh khong dau, toi thieu 2 ky tu, toi da 8
ket qua, truong xep truoc nganh. Thuat toan cong y het tu
`hocphi-info-fe/src/app/api/search/route.ts` (viet lai bang Python — 2 runtime
khac nhau, khong import chung duoc)."""

import unicodedata

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Major, School
from app.schemas.common import SearchHitOut

router = APIRouter(tags=["search"])

MIN_QUERY_LEN = 2
MAX_HITS = 8


def normalize(text: str) -> str:
    """Bo dau tieng Viet + lowercase — vd "Bách khoa" -> "bach khoa"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return without_marks.replace("đ", "d").strip()


@router.get("/api/search", response_model=list[SearchHitOut])
async def search(
    q: str = "",
    session: AsyncSession = Depends(get_session),
) -> list[SearchHitOut]:
    query = normalize(q)
    if len(query) < MIN_QUERY_LEN:
        return []

    schools = (
        await session.scalars(select(School).where(School.deleted_at.is_(None)))
    ).all()
    majors = (
        await session.scalars(select(Major).where(Major.deleted_at.is_(None)))
    ).all()

    school_hits = [
        SearchHitOut(
            kind="school",
            slug=s.slug,
            name=s.name,
            short_name=s.short_name,
        )
        for s in schools
        if query in normalize(f"{s.name} {s.short_name or ''}")
    ]
    major_hits = [
        SearchHitOut(kind="major", slug=m.slug, name=m.name)
        for m in majors
        if query in normalize(m.name)
    ]
    return [*school_hits, *major_hits][:MAX_HITS]
