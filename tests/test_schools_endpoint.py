"""GET /api/schools (S2) — doc VIEW school_track_stats, chi tinh tren he dai
tra. NEU chi co du lieu he chat_luong_cao (Tuan 2) nen KHONG xuat hien trong
danh sach nay — dung ngu nghia "khong tron he" cua schema.md §4.
"""

import csv
from pathlib import Path

import pytest
import scripts.import_school_logos as logo_mod
from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.import_school_logos import main as run_import
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
    assert uit_row["school"]["logoUrl"] is None  # chua chay import_school_logos


async def test_list_schools_exposes_logo_url_after_import(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_seed()
    csv_path = tmp_path / "003_school_logos.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(("slug", "name", "short_name", "logo_url"))
        writer.writerow(("uit", "DH CNTT", "UIT", "https://example.org/uit.png"))
    monkeypatch.setattr(logo_mod, "CSV_PATH", csv_path)
    await run_import()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools")

    rows = resp.json()
    uit_row = next(r for r in rows if r["school"]["slug"] == "uit")
    assert uit_row["school"]["logoUrl"] == "https://example.org/uit.png"


async def test_list_schools_search_matches_by_short_name_without_diacritics(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools", params={"search": "uit"})

    assert resp.status_code == 200
    rows = resp.json()
    slugs = {r["school"]["slug"] for r in rows}
    # Khop qua ten viet tat "UIT" (bo dau, substring). Khong khop het danh sach
    # 9 truong -> search co loc that.
    assert "uit" in slugs
    assert slugs != {
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


async def test_list_schools_search_no_match_returns_empty(
    db: AsyncSession,
) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools", params={"search": "zzzzzz"})

    assert resp.status_code == 200
    assert resp.json() == []
