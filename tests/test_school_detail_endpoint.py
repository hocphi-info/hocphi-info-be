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
        # tdtu: 6 dai_tra (gom Du lich o Phan hieu Khanh Hoa) + 4 chat_luong_cao
        # + 6 tien_tien = 16 chuong trinh trong danh sach programs[].
        resp = await client.get("/api/schools/tdtu")

    assert resp.status_code == 200
    body = resp.json()
    assert body["school"]["slug"] == "tdtu"
    assert "logoUrl" in body["school"]  # co mat trong hop dong (NULL truoc import)
    assert len(body["programs"]) == 16

    # trackStats doc VIEW school_track_stats — migration 0004 loai chuong trinh
    # phan hieu (campus IS NOT NULL): dai_tra = 4 (Ke toan, Thiet ke do hoa,
    # Duoc hoc, Du lich co so chinh), KHONG tinh Du lich + Bao ho lao dong o
    # Khanh Hoa du 2 dong do van nam trong programs[].
    n_programs_by_track = {t["track"]: t["nPrograms"] for t in body["trackStats"]}
    assert n_programs_by_track == {
        "dai_tra": 4,
        "chat_luong_cao": 4,
        "tien_tien": 6,
    }
    dai_tra_stat = next(t for t in body["trackStats"] if t["track"] == "dai_tra")
    assert dai_tra_stat["minAmount"] == 31_260_000  # khong con bi keo xuong 20,5tr

    # Chuong trinh phan hieu van xuat hien trong programs[], co `campus` set.
    du_lich_rows = [
        p for p in body["programs"] if p["program"]["majorSlug"] == "du-lich"
    ]
    assert {p["program"]["campus"] for p in du_lich_rows} == {None, "Khánh Hòa"}

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
