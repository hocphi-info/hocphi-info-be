"""Nap du lieu thu cong — KHONG co admin CRUD API (origin R4).

    uv run python -m scripts.seed

Ba buoc tuan tu, moi buoc tu commit rieng (khong dung 1 transaction lon cho ca
script — neu buoc sau loi, buoc truoc van con, chay lai an toan vi moi buoc
deu idempotent):

  1. seeds/001_schools.sql, seeds/002_majors.sql — file SQL thuan, chay qua
     AsyncSession + `text()`, dua vao `ON CONFLICT ... DO NOTHING` cua chinh
     file SQL (khac app/health.py o cho: script nay tu mo SessionLocal(),
     khong qua Depends — day khong phai HTTP request).
  2. seeds/*.jsonl — output cua AI-crawler, doc tung dong bang
     `crawler.schema.TuitionRow`. KHONG nap het moi dong: chi dong co trong
     `scripts.seed_majors_mapping.ROW_TO_MAJOR_SLUG` (da duyet tay, xem file do
     va docs/plans/2026-09-05-001-...-plan.md § Phu luc) moi duoc nap; dong
     con lai bi bo qua (in ra so luong khi chay xong).

Idempotent: `programs` dung "get or create" (SELECT truoc, INSERT neu thieu,
dua vao UNIQUE (school,major,track,language,campus)); `tuition_records` SELECT
truoc theo UNIQUE (program_id, academic_year), INSERT neu thieu. Chay lai
script nhieu lan khong nhan doi du lieu.
"""

import asyncio
import sys
from pathlib import Path

from app.db import SessionLocal, engine
from app.models import Major, Program, School, TuitionRecord
from crawler.schema import TuitionRow
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_majors_mapping import ROW_TO_MAJOR_SLUG

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"

# Thu tu chay — file sau co the tham chieu du lieu file truoc (vd 002_majors
# khong phu thuoc 001_schools, nhung jsonl phu thuoc ca hai).
SQL_SEED_FILES = [
    "001_schools.sql",
    "002_majors.sql",
]


async def run_sql_seed_file(name: str) -> None:
    path = SEEDS_DIR / name
    if not path.exists():
        print(f"  [bo qua] khong thay {path}")
        return
    sql = path.read_text(encoding="utf-8")
    async with SessionLocal() as session:
        await session.execute(text(sql))
        await session.commit()
    print(f"  [xong] {name}")


async def _get_or_create_program(
    session: AsyncSession,
    *,
    school_id: str,
    major_id: str,
    row: TuitionRow,
) -> str:
    """SELECT truoc theo dung UNIQUE (school,major,track,language,campus) cua
    `programs` (schema.md §3); INSERT neu chua co. Tra ve `programs.id`."""
    campus_filter = (
        Program.campus.is_(None) if row.campus is None else Program.campus == row.campus
    )
    existing = await session.scalar(
        select(Program.id).where(
            Program.school_id == school_id,
            Program.major_id == major_id,
            Program.track == row.track,
            Program.language == row.language,
            campus_filter,
        )
    )
    if existing is not None:
        return existing

    program = Program(
        school_id=school_id,
        major_id=major_id,
        track=row.track,
        language=row.language,
        campus=row.campus,
    )
    session.add(program)
    await session.flush()  # gen_ulid() chay o DB — flush de doc lai program.id
    return program.id


async def _load_jsonl_file(filename: str) -> tuple[int, int]:
    """Tra ve (so_dong_da_nap, so_dong_bo_qua)."""
    mapping = ROW_TO_MAJOR_SLUG.get(filename, {})
    path = SEEDS_DIR / filename
    if not path.exists():
        print(f"  [bo qua] khong thay {path}")
        return 0, 0

    loaded = 0
    skipped = 0
    async with SessionLocal() as session:
        for line_no, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                continue
            major_slug = mapping.get(line_no)
            if major_slug is None:
                skipped += 1
                continue

            row = TuitionRow.model_validate_json(raw_line)

            school_id = await session.scalar(
                select(School.id).where(School.slug == row.school_slug)
            )
            if school_id is None:
                print(
                    f"  [loi] {filename}:{line_no} khong thay "
                    f"school_slug={row.school_slug!r} (chay 001_schools.sql chua?)"
                )
                skipped += 1
                continue

            major_id = await session.scalar(
                select(Major.id).where(Major.slug == major_slug)
            )
            if major_id is None:
                print(
                    f"  [loi] {filename}:{line_no} khong thay "
                    f"major_slug={major_slug!r} (chay 002_majors.sql chua?)"
                )
                skipped += 1
                continue

            program_id = await _get_or_create_program(
                session, school_id=school_id, major_id=major_id, row=row
            )

            existing_tr = await session.scalar(
                select(TuitionRecord.id).where(
                    TuitionRecord.program_id == program_id,
                    TuitionRecord.academic_year == row.academic_year,
                )
            )
            if existing_tr is None:
                session.add(
                    TuitionRecord(
                        program_id=program_id,
                        academic_year=row.academic_year,
                        amount_per_year=row.amount_per_year,
                        unit_original=row.unit_original,
                        amount_original=row.amount_original,
                        credits_per_year_assumed=row.credits_per_year_assumed,
                        duration_years_assumed=row.duration_years_assumed,
                        is_projected=row.is_projected,
                        confidence=row.confidence,
                        needs_review=row.needs_review,
                        review_reason=row.review_reason,
                    )
                )
            loaded += 1
        await session.commit()
    return loaded, skipped


async def main() -> None:
    print(f"Nap seed tu {SEEDS_DIR}")
    for name in SQL_SEED_FILES:
        await run_sql_seed_file(name)

    total_loaded = 0
    total_skipped = 0
    for filename in ROW_TO_MAJOR_SLUG:
        loaded, skipped = await _load_jsonl_file(filename)
        print(f"  [xong] {filename} -> nap {loaded} dong, bo qua {skipped} dong")
        total_loaded += loaded
        total_skipped += skipped

    print(f"Tong: nap {total_loaded} dong, bo qua {total_skipped} dong.")
    await engine.dispose()
    print("Hoan tat.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
