"""Hop dong API: `openapi.json` (commit trong repo) phai khop code, va cac enum
tra cuu phai khop du lieu that.

FE sinh type TypeScript tu `openapi.json` (xem hocphi-info-fe `npm run gen:api`),
nen file nay la "nguon su that" giua hai repo — test do o day thay vi de loi lo
ra luc runtime tren production.
"""

from app.enums import CityCode, MajorGroupCode
from scripts.export_openapi import OPENAPI_PATH, render
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def test_openapi_json_matches_app() -> None:
    assert OPENAPI_PATH.exists(), "Thieu openapi.json — chay `make openapi`."
    assert OPENAPI_PATH.read_text() == render(), (
        "openapi.json khong khop app.openapi() — chay `make openapi` roi commit."
    )


async def test_city_codes_match_lookup_table(db: AsyncSession) -> None:
    rows = (await db.execute(text("SELECT code FROM cities"))).scalars().all()
    assert {c.value for c in CityCode} == set(rows), (
        "Enum CityCode lech bang `cities` — cap nhat app/enums.py."
    )


async def test_major_group_codes_match_lookup_table(db: AsyncSession) -> None:
    rows = (await db.execute(text("SELECT code FROM major_groups"))).scalars().all()
    assert {g.value for g in MajorGroupCode} == set(rows), (
        "Enum MajorGroupCode lech bang `major_groups` — cap nhat app/enums.py."
    )
