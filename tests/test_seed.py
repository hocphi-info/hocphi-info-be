"""Sau `alembic upgrade head`: bang tra cuu co du dong (seed ngay trong migration
0001 qua `op.bulk_insert`). Chay `scripts.seed` nap 50 truong, moi `id` la ULID
(Crockford base32, 26 ky tu, sinh boi `gen_ulid()` o DB).
"""

import re

from app.models import AppSetting, City, MajorGroup, School
from scripts.seed import main as run_seed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


async def test_lookup_tables_seeded_by_migration(db: AsyncSession) -> None:
    cities = (await db.execute(select(City))).scalars().all()
    assert {c.code for c in cities} == {"HCM", "HN"}

    groups = (await db.execute(select(MajorGroup))).scalars().all()
    assert len(groups) == 6

    setting_keys = (await db.execute(select(AppSetting.key))).scalars().all()
    assert set(setting_keys) == {
        "current_intake_year",
        "course_years_default",
        "default_increase_pct",
        "default_increase_band_pct",
    }


async def test_seed_script_loads_50_schools_with_ulid_ids(db: AsyncSession) -> None:
    await run_seed()

    schools = (
        (await db.execute(select(School).where(School.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    assert len(schools) == 50
    for school in schools:
        assert _ULID_RE.match(school.id), f"id khong hop le: {school.id!r}"
