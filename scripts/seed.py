"""Nap du lieu thu cong — KHONG co admin CRUD API (origin R4).

    uv run python -m scripts.seed

Doc file SQL trong seeds/ va thuc thi qua AsyncSession. Idempotent: cac file seed
dung `ON CONFLICT ... DO NOTHING` nen chay lai khong nhan doi.

Khac app/health.py o cho: script nay tu mo SessionLocal() (khong qua Depends —
day khong phai HTTP request).
"""

import asyncio
import sys
from pathlib import Path

from app.db import SessionLocal, engine
from sqlalchemy import text

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"

# Thu tu chay — them file moi vao day khi co (programs, tuition_records...).
SEED_FILES = [
    "001_schools.sql",
]


async def run_seed_file(name: str) -> None:
    path = SEEDS_DIR / name
    if not path.exists():
        print(f"  [bo qua] khong thay {path}")
        return
    sql = path.read_text(encoding="utf-8")
    async with SessionLocal() as session:
        await session.execute(text(sql))
        await session.commit()
    # Dem so dong bang table tuong ung (tam thoi chi co schools).
    async with SessionLocal() as session:
        n = await session.scalar(text("SELECT count(*) FROM schools"))
    print(f"  [xong] {name} -> schools hien co {n} dong")


async def main() -> None:
    print(f"Nap seed tu {SEEDS_DIR}")
    for name in SEED_FILES:
        await run_seed_file(name)
    await engine.dispose()
    print("Hoan tat.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
