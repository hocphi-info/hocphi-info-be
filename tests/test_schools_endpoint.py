"""GET /api/schools (S2) — doc VIEW school_track_stats, chi tinh tren he dai
tra. NEU chi co du lieu he chat_luong_cao (Tuan 2) nen KHONG xuat hien trong
danh sach nay — dung ngu nghia "khong tron he" cua schema.md §4.
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession


async def test_list_schools_empty_when_no_data(db: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_schools_only_includes_schools_with_dai_tra_programs(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools")

    assert resp.status_code == 200
    rows = resp.json()
    slugs = {r["school"]["slug"] for r in rows}
    # cac truong co dong dai_tra da nap; neu chi co chat_luong_cao (rows
    # 4,5,7) nen KHONG xuat hien.
    assert slugs == {
        "tdtu",
        "dh-van-lang",
        "uit",
        "ussh-tphcm",
        "hutech",
        "ulis",
        "dh-hoa-sen",
        "dh-quoc-te-tphcm",
        "dh-khoa-hoc-tu-nhien-tphcm",
    }

    uit_row = next(r for r in rows if r["school"]["slug"] == "uit")
    assert uit_row["stats"]["nPrograms"] == 1
    assert uit_row["stats"]["minAmount"] == 37_000_000
    assert uit_row["stats"]["increaseSummary"] == "—"  # chua seed program_increase
