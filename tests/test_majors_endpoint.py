"""GET /api/majors (S1) — httpx.AsyncClient goi thang app qua ASGITransport
(khong can server that chay), dung chung DB test voi fixture `db` (xem
tests/conftest.py). Response phai dung camelCase, khop
hocphi-info-fe/src/types/domain.ts:MajorRow.
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession


async def test_list_majors_empty_when_no_data(db: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/majors")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_majors_returns_seeded_rows_with_camelcase_shape(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/majors")

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 25

    row = next(
        r
        for r in rows
        if r["program"]["majorSlug"] == "cong-nghe-thong-tin"
        and r["program"]["track"] == "dai_tra"
    )
    assert row["program"]["schoolSlug"] == "uit"
    assert row["school"]["shortName"] == "UIT"
    assert row["major"]["standardYears"] == 4
    assert row["year1"]["amountPerYear"] == 37_000_000
    assert row["year1"]["isProjected"] is False
    assert row["increase"] is None  # chua seed program_increase o Tuan 2
