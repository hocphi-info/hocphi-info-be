"""selectinload chay OK (khong lazy-load ngoai await); vi pham CHECK constraint
o `app/models.py` (majors) -> IntegrityError, dung ngay o DB chu khong doi API
Tuan 2 tu validate.
"""

import pytest
from app.models import Major, School
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def test_selectinload_programs_executes(db: AsyncSession) -> None:
    """Tuan 1 chua co du lieu `programs` — chi can khong nem loi (vi du
    `MissingGreenlet` neu lazy-load nham) la du."""
    result = await db.execute(select(School).options(selectinload(School.programs)))
    result.scalars().all()


async def test_standard_years_check_constraint(db: AsyncSession) -> None:
    db.add(
        Major(
            slug="nganh-thu-nghiem",
            name="Nganh thu nghiem",
            group_code="CNTT",
            standard_years=2,  # CHECK: BETWEEN 3 AND 7
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_practice_profession_required_check_constraint(
    db: AsyncSession,
) -> None:
    db.add(
        Major(
            slug="nganh-hanh-nghe",
            name="Nganh hanh nghe",
            group_code="CNTT",
            requires_practice_license=True,
            practice_profession=None,  # CHECK: bat buoc khi requires_practice_license
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()
