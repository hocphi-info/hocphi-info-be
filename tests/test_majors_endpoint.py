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
    assert len(rows) == 150

    row = next(
        r
        for r in rows
        if r["program"]["majorSlug"] == "cong-nghe-thong-tin"
        and r["program"]["track"] == "dai_tra"
        and r["program"]["schoolSlug"] == "uit"
    )
    assert row["program"]["schoolSlug"] == "uit"
    assert row["school"]["shortName"] == "UIT"
    assert row["school"]["logoUrl"] is None  # chua chay import_school_logos
    assert row["major"]["standardYears"] == 4
    assert row["year1"]["amountPerYear"] == 37_000_000
    assert row["year1"]["isProjected"] is False
    assert row["increase"] is None  # chua seed program_increase o Tuan 2


async def test_list_majors_search_filters_by_major_name_without_diacritics(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/majors", params={"search": "ke toan"})

    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "phai co it nhat 1 dong khop 'ke toan'"
    # Moi dong tra ve deu la nganh Ke toan (khop qua ten nganh, khong dau).
    assert {r["major"]["slug"] for r in rows} == {"ke-toan"}
    # /api/majors tra 1 dong / program -> nhieu truong day Ke toan -> nhieu dong.
    assert len(rows) >= 1


async def test_list_majors_search_also_matches_school_name(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/majors", params={"search": "ton duc thang"}
        )

    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "search theo ten truong phai ra cac chuong trinh cua truong do"
    # Khop qua ten truong -> moi dong deu la cua Ton Duc Thang, nhieu nganh.
    assert {r["school"]["slug"] for r in rows} == {"tdtu"}
    assert len({r["major"]["slug"] for r in rows}) > 1


async def test_list_majors_search_below_min_length_returns_empty(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/majors", params={"search": "a"})

    assert resp.status_code == 200
    assert resp.json() == []
