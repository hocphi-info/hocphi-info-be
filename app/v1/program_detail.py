"""GET /api/schools/{school_slug}/majors/{major_slug} (S3) — chi tiet 1 nganh tai
1 truong, gom TAT CA `programs` khop cap slug do (moi he dao tao/ngon ngu/co so —
schema.md §3). Khac `app/majors.py` o 2 diem: (1) 2 path param thay vi khong tham
so, co nhanh 404; (2) tinh 2 gia tri dan xuat con lai cua schema.md §5
(`total_course`, `total_with_license`) bang vong lap luy tien trong Python, cong
tu `hocphi-info-fe/src/lib/derive.ts:totalCourseCost()`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_session
from app.enums import CityCode, ProgramLanguage
from app.models import (
    AppSetting,
    Major,
    PostGradRequirement,
    Program,
    ProgramIncrease,
    School,
    Source,
    TaxonomyNode,
    TuitionRecord,
)
from app.queries import latest_published_tuition_subquery
from app.schemas.common import (
    ProgramDetailOut,
    ProgramDetailResponseOut,
    ProgramIncreaseOut,
    ProgramOut,
    RelatedMajorOut,
    SchoolOut,
    SourceOut,
    TuitionRecordOut,
    YearlyAmountOut,
)
from app.taxonomy import MajorContext, load_major_context, to_major_out
from app.v1.schools import STATS_TRACK

router = APIRouter(tags=["program-detail"])

# So nganh gan hien toi da tren trang chi tiet.
RELATED_MAJORS_LIMIT = 6


def _compute_yearly_amounts(
    year1_amount: int, year1_academic_year: str, years: int, increase_pct: float
) -> list[YearlyAmountOut]:
    """Nam 1 = so cong bo; nam 2..N tinh luy tien theo `increase_pct`/nam. Cong
    tu derive.ts:totalCourseCost() — lam tron TUNG nam (khong lam tron sau khi
    cong tong) de tong hien thi luon khop dung tong cac dong bang FE se hien."""
    start_year = int(year1_academic_year.split("-")[0])
    amount = float(year1_amount)
    out: list[YearlyAmountOut] = []
    for i in range(years):
        out.append(
            YearlyAmountOut(
                academic_year=f"{start_year + i}-{start_year + i + 1}",
                amount_per_year=round(amount),
                is_projected=i > 0,
            )
        )
        amount *= 1 + increase_pct / 100
    return out


async def _related_majors(
    session: AsyncSession, major: Major, ctx: MajorContext
) -> list[RelatedMajorOut]:
    """Nganh CUNG NHOM NGANH (cha 5 so cua ma nganh) co du lieu hoc phi, khong tinh
    chinh nganh dang xem. So truong + khoang hoc phi Nam 1 chi tren he DAI TRA
    (STATS_TRACK) — dung nguyen tac "khong tron he" cua S2. Nganh chua phan loai
    (khong co nhom) -> rong."""
    taxonomy = ctx.taxonomy.get(major.code) if major.code is not None else None
    if taxonomy is None:
        return []

    latest_tr = latest_published_tuition_subquery()
    amount = latest_tr.c.amount_per_year
    rows = (
        await session.execute(
            select(
                Major.slug,
                Major.name,
                func.count(distinct(Program.school_id)),
                func.min(amount),
                func.max(amount),
            )
            .select_from(Program)
            .join(Major, Major.id == Program.major_id)
            .join(School, School.id == Program.school_id)
            .join(TaxonomyNode, TaxonomyNode.code == Major.code)
            .join(latest_tr, latest_tr.c.program_id == Program.id)
            .where(
                TaxonomyNode.parent_code == taxonomy.group.code,
                Major.id != major.id,
                Program.track == STATS_TRACK,
                Program.deleted_at.is_(None),
                Major.deleted_at.is_(None),
                School.deleted_at.is_(None),
            )
            .group_by(Major.id, Major.slug, Major.name)
            .order_by(func.count(distinct(Program.school_id)).desc(), Major.name)
            .limit(RELATED_MAJORS_LIMIT)
        )
    ).all()
    return [
        RelatedMajorOut(
            slug=slug,
            name=name,
            n_schools=n_schools,
            min_year1_amount=min_amount,
            max_year1_amount=max_amount,
        )
        for slug, name, n_schools, min_amount, max_amount in rows
    ]


@router.get(
    "/api/v1/schools/{school_slug}/majors/{major_slug}",
    response_model=ProgramDetailResponseOut,
)
async def get_program_detail(
    school_slug: str,
    major_slug: str,
    session: AsyncSession = Depends(get_session),
) -> ProgramDetailResponseOut:
    latest_tr = latest_published_tuition_subquery()
    LatestTuition = aliased(TuitionRecord, latest_tr)

    stmt = (
        select(Program, School, Major, LatestTuition, ProgramIncrease, Source)
        .join(School, Program.school_id == School.id)
        .join(Major, Program.major_id == Major.id)
        .join(latest_tr, latest_tr.c.program_id == Program.id)
        .outerjoin(ProgramIncrease, ProgramIncrease.program_id == Program.id)
        # outerjoin: source_id nullable tren tuition_records (F12) — chi Nam 1
        # (ban ghi that) co the co nguon, cac nam du phong la so tinh.
        .outerjoin(Source, Source.id == latest_tr.c.source_id)
        .where(
            School.slug == school_slug,
            Major.slug == major_slug,
            Program.deleted_at.is_(None),
            School.deleted_at.is_(None),
            Major.deleted_at.is_(None),
        )
        # campus NULLS FIRST: co so chinh luon dung truoc phan hieu trong danh
        # sach cac he dao tao cua cap (school, major).
        .order_by(Program.track, Program.campus.nulls_first(), Program.language)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Program not found")

    _, school, major, _, _, _ = rows[0]

    default_increase_pct = float(
        await session.scalar(
            select(AppSetting.value).where(AppSetting.key == "default_increase_pct")
        )
    )
    post_grad_total = await session.scalar(
        select(func.coalesce(func.sum(PostGradRequirement.cost_max), 0)).where(
            PostGradRequirement.major_id == major.id,
            PostGradRequirement.deleted_at.is_(None),
        )
    )
    assert post_grad_total is not None  # COALESCE(..., 0) luon ra 1 gia tri

    programs: list[ProgramDetailOut] = []
    for program, _school, _major, year1, increase, source in rows:
        increase_pct = (
            float(increase.annual_increase_pct)
            if increase is not None
            else default_increase_pct
        )
        yearly_amounts = _compute_yearly_amounts(
            year1.amount_per_year,
            year1.academic_year,
            major.standard_years,
            increase_pct,
        )
        total_course = sum(a.amount_per_year for a in yearly_amounts)
        programs.append(
            ProgramDetailOut(
                program=ProgramOut(
                    id=program.id,
                    school_slug=school.slug,
                    major_slug=major.slug,
                    track=program.track,
                    language=ProgramLanguage(program.language),
                    campus=program.campus,
                    display_name=program.display_name,
                ),
                year1=TuitionRecordOut(
                    program_id=year1.program_id,
                    academic_year=year1.academic_year,
                    amount_per_year=year1.amount_per_year,
                    is_projected=year1.is_projected,
                    confidence=year1.confidence,
                    source=(
                        SourceOut(
                            url=source.url,
                            doc_type=source.doc_type,
                            published_date=source.published_date,
                        )
                        if source is not None
                        else None
                    ),
                ),
                increase=(
                    ProgramIncreaseOut(
                        program_id=increase.program_id,
                        annual_increase_pct=float(increase.annual_increase_pct),
                        increase_source=increase.increase_source,
                    )
                    if increase is not None
                    else None
                ),
                yearly_amounts=yearly_amounts,
                total_course=total_course,
                total_with_license=total_course + post_grad_total,
            )
        )

    ctx = await load_major_context(session, [major])

    return ProgramDetailResponseOut(
        school=SchoolOut(
            slug=school.slug,
            name=school.name,
            short_name=school.short_name,
            city_code=CityCode(school.city_code),
            category=school.category,
            logo_url=school.logo_url,
        ),
        major=to_major_out(major, ctx),
        programs=programs,
        related_majors=await _related_majors(session, major, ctx),
    )
