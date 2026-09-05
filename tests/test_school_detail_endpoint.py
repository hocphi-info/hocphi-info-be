"""GET /api/schools/{school_slug} (F7) — httpx.AsyncClient goi thang app qua
ASGITransport, dung chung DB test voi fixture `db`. Response phai dung
camelCase, khop pattern tests/test_program_detail_endpoint.py.
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession


async def test_get_school_detail_404_when_school_not_found(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/khong-ton-tai")
    assert resp.status_code == 404


async def test_get_school_detail_multi_track(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # tdtu: 5 dai_tra + 4 chat_luong_cao + 6 tien_tien = 15 chuong trinh.
        resp = await client.get("/api/schools/tdtu")

    assert resp.status_code == 200
    body = resp.json()
    assert body["school"]["slug"] == "tdtu"
    assert "logoUrl" in body["school"]  # co mat trong hop dong (NULL truoc import)
    assert len(body["programs"]) == 15

    n_programs_by_track = {t["track"]: t["nPrograms"] for t in body["trackStats"]}
    assert n_programs_by_track == {
        "dai_tra": 5,
        "chat_luong_cao": 4,
        "tien_tien": 6,
    }
    # F12 khong lap lai o F7 — source luon None tren tung dong chuong trinh.
    assert all(p["year1"]["source"] is None for p in body["programs"])


async def test_get_school_detail_single_program_school(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/dh-van-lang")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["programs"]) == 1
    assert len(body["trackStats"]) == 1
    only_track = body["trackStats"][0]
    assert only_track["nPrograms"] == 1
    assert only_track["minAmount"] == only_track["maxAmount"]
