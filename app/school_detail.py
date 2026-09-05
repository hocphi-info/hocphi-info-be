"""GET /api/schools/{school_slug} (F7) — chi tiet 1 truong: ho so + toan bo
chuong trinh da co du lieu (moi he dao tao) + Min-Max theo he. Tai dung VIEW
`school_track_stats` (schema.md §4) nhung loc theo `school_id` thay vi `track`
(khac `app/schools.py` — S2 loc theo 1 track co dinh cho TAT CA truong, o day
loc theo 1 truong co dinh cho TAT CA track) nen khong can migration moi.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_session
from app.models import Major, Program, School, TuitionRecord
from app.queries import latest_published_tuition_subquery
from app.schemas.common import (
    MajorOut,
    ProgramOut,
    SchoolDetailResponseOut,
    SchoolOut,
    SchoolProgramRowOut,
    SchoolTrackStatOut,
    TuitionRecordOut,
)

router = APIRouter(tags=["school-detail"])


@router.get("/api/schools/{school_slug}", response_model=SchoolDetailResponseOut)
async def get_school_detail(
    school_slug: str,
    session: AsyncSession = Depends(get_session),
) -> SchoolDetailResponseOut:
    school = await session.scalar(
        select(School).where(
            School.slug == school_slug, School.deleted_at.is_(None)
        )
    )
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    track_rows = (
        await session.execute(
            text(
                "SELECT track, n_programs, min_amount, max_amount, "
                "median_amount, min_major_id, max_major_id "
                "FROM school_track_stats WHERE school_id = :school_id"
            ),
            {"school_id": school.id},
        )
    ).all()
    if not track_rows:
        raise HTTPException(status_code=404, detail="School has no seeded programs")

    majors = {
        m.id: m
        for m in (
            await session.scalars(select(Major).where(Major.deleted_at.is_(None)))
        ).all()
    }
    track_stats = [
        SchoolTrackStatOut(
            track=row.track,
            n_programs=row.n_programs,
            min_amount=row.min_amount,
            min_major_name=majors[row.min_major_id].name,
            median_amount=float(row.median_amount),
            max_amount=row.max_amount,
            max_major_name=majors[row.max_major_id].name,
        )
        for row in track_rows
    ]

    latest_tr = latest_published_tuition_subquery()
    LatestTuition = aliased(TuitionRecord, latest_tr)
    program_rows = (
        await session.execute(
            select(Program, Major, LatestTuition)
            .join(Major, Program.major_id == Major.id)
            .join(latest_tr, latest_tr.c.program_id == Program.id)
            .where(
                Program.school_id == school.id,
                Program.deleted_at.is_(None),
                Major.deleted_at.is_(None),
            )
            .order_by(Major.name, Program.track, Program.language)
        )
    ).all()

    return SchoolDetailResponseOut(
        school=SchoolOut(
            slug=school.slug,
            name=school.name,
            short_name=school.short_name,
            city_code=school.city_code,
            category=school.category.value,
        ),
        track_stats=track_stats,
        programs=[
            SchoolProgramRowOut(
                program=ProgramOut(
                    id=program.id,
                    school_slug=school.slug,
                    major_slug=major.slug,
                    track=program.track.value,
                    language=program.language,
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
            )
            for program, major, year1 in program_rows
        ],
    )
