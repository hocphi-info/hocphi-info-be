"""`scripts.seed` nap seeds/*.jsonl theo `scripts.seed_majors_mapping` — chi 25/43
dong duoc duyet moi vao DB; con lai bi bo qua. Chay lai script khong nhan doi
(idempotent) du programs/tuition_records dung "get or create" thay vi
`ON CONFLICT` nhu 2 file *.sql.
"""

from app.models import Major, Program, TuitionRecord
from scripts.seed import main as run_seed
from scripts.seed_majors_mapping import ROW_TO_MAJOR_SLUG
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

EXPECTED_LOADED_ROWS = 25


async def test_seed_loads_only_approved_rows(db: AsyncSession) -> None:
    await run_seed()

    n_majors = await db.scalar(select(func.count()).select_from(Major))
    assert n_majors == len(
        {slug for mapping in ROW_TO_MAJOR_SLUG.values() for slug in mapping.values()}
    )

    n_programs = await db.scalar(select(func.count()).select_from(Program))
    n_tuition = await db.scalar(select(func.count()).select_from(TuitionRecord))
    assert n_programs == EXPECTED_LOADED_ROWS
    assert n_tuition == EXPECTED_LOADED_ROWS


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
