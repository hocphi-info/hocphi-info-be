"""`scripts.seed` nap seeds/*.jsonl theo `scripts.seed_majors_mapping` — chi
dong co trong dict cua file do moi vao DB; con lai bi bo qua (vd uet.jsonl/
ueb.jsonl khong co trong dict nao nen bi bo qua toan bo — major_name_raw cua
2 file do la ten nhom/he chung, khong phai ten nganh cu the). Chay lai script
khong nhan doi (idempotent) du programs/tuition_records dung "get or create"
thay vi `ON CONFLICT` nhu 2 file *.sql.
"""

from app.models import Major, Program, School, TuitionRecord
from scripts.seed import main as run_seed
from scripts.seed_majors_mapping import ROW_TO_MAJOR_SLUG
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _mapped_slugs() -> set[str]:
    """Moi slug xuat hien trong ROW_TO_MAJOR_SLUG — gia tri co the la str hoac
    list[str] (fan-out, xem scripts/seed_majors_mapping.py)."""
    out: set[str] = set()
    for mapping in ROW_TO_MAJOR_SLUG.values():
        for value in mapping.values():
            out.update([value] if isinstance(value, str) else value)
    return out


# 179 (tong cac slot mapping da co, khong con dong nao bi skip vi thieu major)
# + 51 HCMUT: dong 1 (he Chuong trinh tieu chuan) fan-out ra 41 nganh, dong 2-8
# them 10 nganh nua. Xem scripts/seed_majors_mapping.py "dh-bach-khoa-tphcm.jsonl".
# (Con so cu 151 da lac hau tu truoc dot nay — nhieu file mapping them vao ma
# khong cap nhat hang so; 179 la baseline dung trên main.)
EXPECTED_LOADED_ROWS = 230


async def test_seed_loads_only_approved_rows(db: AsyncSession) -> None:
    await run_seed()

    n_majors = await db.scalar(select(func.count()).select_from(Major))
    assert n_majors == len(_mapped_slugs())

    n_programs = await db.scalar(select(func.count()).select_from(Program))
    n_tuition = await db.scalar(select(func.count()).select_from(TuitionRecord))
    assert n_programs == EXPECTED_LOADED_ROWS
    assert n_tuition == EXPECTED_LOADED_ROWS


async def test_seed_fans_out_one_jsonl_line_to_many_programs(db: AsyncSession) -> None:
    """HCMUT he Chuong trinh tieu chuan: 1 dong seeds/dh-bach-khoa-tphcm.jsonl
    (major_slug=null, mapping tra ve list 41 slug) -> 41 `programs` khac major_id
    nhung cung amount_per_year va cung `source`."""
    await run_seed()

    school_id = await db.scalar(
        select(School.id).where(School.slug == "dh-bach-khoa-tphcm")
    )
    rows = (
        (
            await db.execute(
                select(TuitionRecord)
                .join(Program, Program.id == TuitionRecord.program_id)
                .where(
                    Program.school_id == school_id,
                    Program.track == "dai_tra",
                    Program.language == "vi",
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 41
    assert {r.amount_per_year for r in rows} == {31_500_000}
    assert len({r.source_id for r in rows}) == 1
    assert len({r.program_id for r in rows}) == 41


async def test_seed_is_idempotent_on_second_run(db: AsyncSession) -> None:
    await run_seed()
    await run_seed()

    n_programs = await db.scalar(select(func.count()).select_from(Program))
    n_tuition = await db.scalar(select(func.count()).select_from(TuitionRecord))
    assert n_programs == EXPECTED_LOADED_ROWS
    assert n_tuition == EXPECTED_LOADED_ROWS


async def test_seed_keeps_needs_review_and_review_reason_from_jsonl(
    db: AsyncSession,
) -> None:
    """Dong nhom C (1 gia dung chung ca nhom, chi nap cho nganh duoc neu ten)
    phai giu nguyen needs_review=true + review_reason tu crawler — khong bi
    xoa khi nap qua migration 0002."""
    await run_seed()

    flagged = (
        (
            await db.execute(
                select(TuitionRecord).where(TuitionRecord.needs_review.is_(True))
            )
        )
        .scalars()
        .all()
    )
    assert len(flagged) > 0
    assert all(row.review_reason for row in flagged)
