"""GET /api/majors (S1) — danh sach 1 dong / chuong trinh, ghep du ngu canh
truong+nganh+hoc phi Nam 1+% tang. Cung khung voi app/health.py: APIRouter +
Depends(get_session) + 1 (bo) query + tra Pydantic response model — chi khac
o day query join 4 bang thay vi SELECT 1.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_session
from app.models import Major, Program, ProgramIncrease, School, TuitionRecord
from app.queries import latest_published_tuition_subquery
from app.schemas.common import (
    MajorOut,
    MajorRowOut,
    ProgramIncreaseOut,
    ProgramOut,
    SchoolOut,
    TuitionRecordOut,
)
from app.text import MIN_QUERY_LEN, normalize

router = APIRouter(tags=["majors"])


@router.get("/api/majors", response_model=list[MajorRowOut])
async def list_majors(
    search: str | None = Query(
        None,
        description=(
            "Loc theo TEN NGANH, bo dau, khong phan biet hoa/thuong. "
            f"Toi thieu {MIN_QUERY_LEN} ky tu sau khi chuan hoa; ngan hon -> tra []."
        ),
    ),
    # --- Phan trang / sap xep: CHUA implement (noi khi FE co UI "Xem them") ---
    # page: int = Query(1, ge=1, description="Trang, 1-based"),
    # per_page: int = Query(50, ge=1, le=200, alias="perPage"),
    # sort: str | None = Query(None, description="vd 'year1' | '-year1' | 'name'"),
    session: AsyncSession = Depends(get_session),
) -> list[MajorRowOut]:
    latest_tr = latest_published_tuition_subquery()
    LatestTuition = aliased(TuitionRecord, latest_tr)

    stmt = (
        select(Program, School, Major, LatestTuition, ProgramIncrease)
        .join(School, Program.school_id == School.id)
        .join(Major, Program.major_id == Major.id)
        # INNER join co y: chuong trinh chua co hoc phi cong bo nao thi chua
        # co gi de hien o S1 — khong hien dong "thieu du lieu".
        .join(latest_tr, latest_tr.c.program_id == Program.id)
        .outerjoin(ProgramIncrease, ProgramIncrease.program_id == Program.id)
        .where(
            Program.deleted_at.is_(None),
            School.deleted_at.is_(None),
            Major.deleted_at.is_(None),
        )
        .order_by(School.name, Major.name)
    )
    rows = (await session.execute(stmt)).all()

    result = [
        MajorRowOut(
            program=ProgramOut(
                id=program.id,
                school_slug=school.slug,
                major_slug=major.slug,
                track=program.track.value,
                language=program.language,
            ),
            school=SchoolOut(
                slug=school.slug,
                name=school.name,
                short_name=school.short_name,
                city_code=school.city_code,
                category=school.category.value,
                logo_url=school.logo_url,
            ),
            major=MajorOut(
                slug=major.slug,
                name=major.name,
                code=major.code,
                group_code=major.group_code,
                standard_years=major.standard_years,
                requires_practice_license=major.requires_practice_license,
                practice_profession=major.practice_profession,
            ),
            year1=TuitionRecordOut(
                program_id=year1.program_id,
                academic_year=year1.academic_year,
                amount_per_year=year1.amount_per_year,
                is_projected=year1.is_projected,
                confidence=year1.confidence.value,
            ),
            increase=(
                ProgramIncreaseOut(
                    program_id=increase.program_id,
                    annual_increase_pct=float(increase.annual_increase_pct),
                    increase_source=increase.increase_source.value,
                )
                if increase is not None
                else None
            ),
        )
        for program, school, major, year1, increase in rows
    ]

    # `search`: loc theo ten nganh (chi thuc the chinh cua endpoint nay —
    # QuickSearch goi rieng /api/schools?search= cho goi y truong). Loc trong
    # Python bang normalize() y het /api/search cu — Postgres bo dau can
    # extension `unaccent`, chua muon them ha tang o MVP.
    if search is not None:
        q = normalize(search)
        if len(q) < MIN_QUERY_LEN:
            return []
        result = [r for r in result if q in normalize(r.major.name)]

    return result
