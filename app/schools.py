"""GET /api/schools (S2) — 1 dong / truong: Min-Max/trung vi hoc phi he dai
tra (doc VIEW `school_track_stats`, schema.md §4) + `increaseSummary` tinh o
day — cong tu `hocphi-info-fe/src/lib/derive.ts:schoolTuitionStats()`, Tuan 2
chuyen logic nay sang BE dung nguyen tac schema.md §5 "gia tri dan xuat tinh
o API" (owner chot khi lap plan, xem docs/plans/2026-09-05-001-...-plan.md).
"""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import enums
from app.db import get_session
from app.models import Major, Program, ProgramIncrease, School
from app.schemas.common import SchoolOut, SchoolRowOut, SchoolStatsOut

router = APIRouter(tags=["schools"])

# "Co so tinh khoang" mac dinh: chi he dai tra — giu dung hanh vi FE Tuan 1-3
# (derive.ts goi schoolTuitionStats voi tracks=["dai_tra"] mac dinh). Doi he/
# gop them CLC la bo loc S2 sau nay — ngoai pham vi Tuan 2.
STATS_TRACK = enums.ProgramTrack.DAI_TRA


def _format_increase_summary(pairs: list[tuple[float, str]]) -> str:
    """Cong tu derive.ts:schoolTuitionStats() — luon nhan danh sach % tang da
    loc dung 1 truong + STATS_TRACK (khong bao gio tron he trong 1 phep tinh)."""
    if not pairs:
        return "—"
    percents = [p for p, _ in pairs]
    sources = {s for _, s in pairs}
    if len(sources) > 1:
        return "hỗn hợp"
    lo, hi = min(percents), max(percents)
    if len(percents) == 1 or lo == hi:
        return f"+{percents[0]:g}%"
    return f"+{lo:g}–{hi:g}%"  # noqa: RUF001 — en dash co y, khop derive.ts


@router.get("/api/schools", response_model=list[SchoolRowOut])
async def list_schools(
    session: AsyncSession = Depends(get_session),
) -> list[SchoolRowOut]:
    # VIEW da tinh san Min-Max/trung vi/so nganh — doc qua SQL Core (chi doc,
    # khong co model ORM rieng cho VIEW).
    view_rows = (
        await session.execute(
            text(
                "SELECT school_id, n_programs, min_amount, max_amount, "
                "median_amount, min_major_id, max_major_id "
                "FROM school_track_stats WHERE track = :track"
            ),
            {"track": STATS_TRACK.value},
        )
    ).all()
    if not view_rows:
        return []

    schools = {
        s.id: s
        for s in (
            await session.scalars(select(School).where(School.deleted_at.is_(None)))
        ).all()
    }
    majors = {
        m.id: m
        for m in (
            await session.scalars(select(Major).where(Major.deleted_at.is_(None)))
        ).all()
    }

    # % tang tung program (truong, STATS_TRACK) — gom theo school_id de tinh
    # increaseSummary. Rong o Tuan 2 (chua seed program_increase nao) -> moi
    # truong tra "—", dung ngu nghia (chua co % tang cong bo).
    increase_by_school: dict[str, list[tuple[float, str]]] = defaultdict(list)
    incr_rows = await session.execute(
        select(
            Program.school_id,
            ProgramIncrease.annual_increase_pct,
            ProgramIncrease.increase_source,
        )
        .join(ProgramIncrease, ProgramIncrease.program_id == Program.id)
        .where(
            Program.track == STATS_TRACK,
            Program.deleted_at.is_(None),
            ProgramIncrease.deleted_at.is_(None),
        )
    )
    for school_id, pct, source in incr_rows:
        increase_by_school[school_id].append((float(pct), source.value))

    result: list[SchoolRowOut] = []
    for view_row in view_rows:
        school = schools.get(view_row.school_id)
        if school is None:
            continue
        min_major = majors.get(view_row.min_major_id)
        max_major = majors.get(view_row.max_major_id)
        result.append(
            SchoolRowOut(
                school=SchoolOut(
                    slug=school.slug,
                    name=school.name,
                    short_name=school.short_name,
                    city_code=school.city_code,
                    category=school.category.value,
                ),
                stats=SchoolStatsOut(
                    n_programs=view_row.n_programs,
                    min_amount=view_row.min_amount,
                    min_major_name=min_major.name if min_major else "",
                    median_amount=float(view_row.median_amount),
                    max_amount=view_row.max_amount,
                    max_major_name=max_major.name if max_major else "",
                    increase_summary=_format_increase_summary(
                        increase_by_school.get(school.id, [])
                    ),
                ),
            )
        )
    result.sort(key=lambda r: r.school.name)
    return result
