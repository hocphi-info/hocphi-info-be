"""GET /api/coverage — do phu du lieu cho trang "Du lieu & nguon" (S/F14) cua FE.

Endpoint doc thu 5, cung khung app/health.py: APIRouter + Depends(get_session) +
query + Pydantic response model. Khac 4 endpoint kia o cho: khong tra "dong du
lieu" ma tra SO DEM (tong hop + theo thanh pho / loai truong / nhom nganh + bang
tung truong).

Nguyen tac: **mot subquery `pub`** = "1 dong / tuition_record da cong bo"
(`deleted_at IS NULL AND is_projected = false`, join programs + majors chua xoa
mem — dung dinh nghia voi CTE `latest` trong VIEW school_track_stats, schema.md
§4). Moi phep dem deu bat nguon tu `pub` nen cac so cong khop nhau:

  Σ byCity.schoolsWithData == Σ byCategory.schoolsWithData == totals.schoolsWithData
  Σ byMajorGroup.programsWithTuition == Σ schools.nPrograms
      == totals.programsWithTuition
  Σ byCity.schoolsTotal == totals.schoolsTotal

Model Pydantic colocate o day (khong vao schemas/common.py) vi chi endpoint nay
dung. camelCase tu sinh qua CamelModel; `hocphi-info-fe/src/types/domain.ts`
nhom `Coverage*` la hop dong doi ung.
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import City, Major, MajorGroup, Program, School, Source, TuitionRecord
from app.schemas.common import CamelModel

router = APIRouter(tags=["coverage"])


# ── Response models ─────────────────────────────────────────────────────────
class CoverageTotalsOut(CamelModel):
    schools_total: int
    schools_with_data: int
    programs_with_tuition: int
    tuition_records: int
    sources_cited: int


class CoverageCityRowOut(CamelModel):
    city_code: str
    city_name: str
    schools_total: int
    schools_with_data: int


class CoverageCategoryRowOut(CamelModel):
    category: str
    schools_total: int
    schools_with_data: int


class CoverageMajorGroupRowOut(CamelModel):
    group_code: str
    group_name: str
    programs_with_tuition: int


class CoverageSchoolRowOut(CamelModel):
    slug: str
    name: str
    short_name: str | None
    city_code: str
    category: str
    n_programs: int
    # doc_type + ngay cua `source` moi nhat trong so cac ban ghi da cong bo cua
    # truong; None khi truong chua co source nao (confidence != verified). FE map
    # doc_type -> nhan nguoi doc ("De an TS 2026"), None -> "—".
    latest_source_doc_type: str | None
    latest_source_date: date | None
    last_updated: date | None


class CoverageOut(CamelModel):
    snapshot_date: date | None
    totals: CoverageTotalsOut
    by_city: list[CoverageCityRowOut]
    by_category: list[CoverageCategoryRowOut]
    by_major_group: list[CoverageMajorGroupRowOut]
    schools: list[CoverageSchoolRowOut]


# ── Endpoint ───────────────────────────────────────────────────────────────
@router.get("/api/coverage", response_model=CoverageOut)
async def get_coverage(
    session: AsyncSession = Depends(get_session),
) -> CoverageOut:
    # `pub`: 1 dong / tuition_record DA CONG BO. Tai dung o moi query ben duoi.
    pub = (
        select(
            TuitionRecord.program_id.label("program_id"),
            TuitionRecord.source_id.label("source_id"),
            TuitionRecord.updated_at.label("tr_updated_at"),
            Program.school_id.label("school_id"),
            Major.group_code.label("group_code"),
        )
        .join(Program, Program.id == TuitionRecord.program_id)
        .join(Major, Major.id == Program.major_id)
        .where(
            TuitionRecord.deleted_at.is_(None),
            TuitionRecord.is_projected.is_(False),
            Program.deleted_at.is_(None),
            Major.deleted_at.is_(None),
        )
        .subquery("pub")
    )
    # Tap school_id co du lieu — dung trong FILTER (WHERE ...) cua byCity/byCategory.
    schools_with_data = select(pub.c.school_id)

    # --- totals + snapshot: 1 round-trip, moi so la 1 scalar subquery tren `pub` ---
    totals_row = (
        await session.execute(
            select(
                select(func.count())
                .select_from(School)
                .where(School.deleted_at.is_(None))
                .scalar_subquery(),
                select(func.count(distinct(pub.c.school_id))).scalar_subquery(),
                select(func.count(distinct(pub.c.program_id))).scalar_subquery(),
                select(func.count()).select_from(pub).scalar_subquery(),
                select(func.count(distinct(pub.c.source_id))).scalar_subquery(),
                select(func.max(pub.c.tr_updated_at)).scalar_subquery(),
            )
        )
    ).one()
    (
        schools_total,
        schools_with_data_n,
        programs_with_tuition,
        tuition_records_n,
        sources_cited,
        snapshot_dt,
    ) = totals_row

    # --- byCity: moi thanh pho trong `cities` (LEFT JOIN giu ca dong = 0) ---
    city_rows = (
        await session.execute(
            select(
                City.code,
                City.name,
                func.count(School.id),
                func.count(School.id).filter(School.id.in_(schools_with_data)),
            )
            .select_from(City)
            .outerjoin(
                School,
                and_(School.city_code == City.code, School.deleted_at.is_(None)),
            )
            .group_by(City.code, City.name)
            .order_by(City.code)
        )
    ).all()

    # --- byCategory: moi gia tri enum co >=1 truong con song ---
    category_rows = (
        await session.execute(
            select(
                School.category,
                func.count(School.id),
                func.count(School.id).filter(School.id.in_(schools_with_data)),
            )
            .where(School.deleted_at.is_(None))
            .group_by(School.category)
            .order_by(School.category)
        )
    ).all()

    # --- byMajorGroup: ca 6 nhom, ke ca = 0 (LEFT JOIN tu major_groups) ---
    group_rows = (
        await session.execute(
            select(
                MajorGroup.code,
                MajorGroup.name,
                func.count(distinct(pub.c.program_id)),
            )
            .select_from(MajorGroup)
            .outerjoin(pub, pub.c.group_code == MajorGroup.code)
            .group_by(MajorGroup.code, MajorGroup.name)
            .order_by(MajorGroup.code)
        )
    ).all()

    # --- schools[]: TAT CA truong con song + so lieu gop tu `pub` + source moi nhat ---
    per_school = (
        select(
            pub.c.school_id.label("school_id"),
            func.count(distinct(pub.c.program_id)).label("n_programs"),
            func.max(pub.c.tr_updated_at).label("last_updated"),
        )
        .group_by(pub.c.school_id)
        .subquery("per_school")
    )
    # DISTINCT ON (school_id): source moi nhat theo published_date (NULLS LAST) roi
    # created_at — cung ky thuat voi app/queries.py:latest_published_tuition_subquery.
    latest_src = (
        select(
            pub.c.school_id.label("school_id"),
            Source.doc_type.label("doc_type"),
            Source.published_date.label("published_date"),
        )
        .join(Source, Source.id == pub.c.source_id)
        .order_by(
            pub.c.school_id,
            Source.published_date.desc().nullslast(),
            Source.created_at.desc(),
        )
        .distinct(pub.c.school_id)
        .subquery("latest_src")
    )
    school_rows = (
        await session.execute(
            select(
                School.slug,
                School.name,
                School.short_name,
                School.city_code,
                School.category,
                func.coalesce(per_school.c.n_programs, 0),
                per_school.c.last_updated,
                latest_src.c.doc_type,
                latest_src.c.published_date,
            )
            .select_from(School)
            .outerjoin(per_school, per_school.c.school_id == School.id)
            .outerjoin(latest_src, latest_src.c.school_id == School.id)
            .where(School.deleted_at.is_(None))
            .order_by(func.coalesce(per_school.c.n_programs, 0).desc(), School.name)
        )
    ).all()

    return CoverageOut(
        snapshot_date=snapshot_dt.date() if snapshot_dt is not None else None,
        totals=CoverageTotalsOut(
            schools_total=schools_total,
            schools_with_data=schools_with_data_n,
            programs_with_tuition=programs_with_tuition,
            tuition_records=tuition_records_n,
            sources_cited=sources_cited,
        ),
        by_city=[
            CoverageCityRowOut(
                city_code=code,
                city_name=name,
                schools_total=total,
                schools_with_data=with_data,
            )
            for code, name, total, with_data in city_rows
        ],
        by_category=[
            CoverageCategoryRowOut(
                category=category.value,
                schools_total=total,
                schools_with_data=with_data,
            )
            for category, total, with_data in category_rows
        ],
        by_major_group=[
            CoverageMajorGroupRowOut(
                group_code=code,
                group_name=name,
                programs_with_tuition=n,
            )
            for code, name, n in group_rows
        ],
        schools=[
            CoverageSchoolRowOut(
                slug=slug,
                name=name,
                short_name=short_name,
                city_code=city_code,
                category=category.value,
                n_programs=n_programs,
                latest_source_doc_type=(
                    doc_type.value if doc_type is not None else None
                ),
                latest_source_date=published_date,
                last_updated=last_updated.date() if last_updated is not None else None,
            )
            for (
                slug,
                name,
                short_name,
                city_code,
                category,
                n_programs,
                last_updated,
                doc_type,
                published_date,
            ) in school_rows
        ],
    )
