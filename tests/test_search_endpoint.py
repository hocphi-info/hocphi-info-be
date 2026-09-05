"""GET /api/search?q= (F13) — khong dau, toi thieu 2 ky tu, toi da 8 ket qua,
truong xep truoc nganh (cong y het hocphi-info-fe/src/app/api/search/route.ts).
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession


async def test_search_below_min_length_returns_empty(db: AsyncSession) -> None:
    await run_seed()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/search", params={"q": "a"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_search_matches_major_without_diacritics(db: AsyncSession) -> None:
    await run_seed()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/search", params={"q": "ke toan"})

    assert resp.status_code == 200
    hits = resp.json()
    expected = {
        "kind": "major",
        "slug": "ke-toan",
        "name": "Kế toán",
        "shortName": None,
    }
    assert expected in hits


async def test_search_matches_school_by_short_name(db: AsyncSession) -> None:
    await run_seed()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/search", params={"q": "uit"})

    assert resp.status_code == 200
    hits = resp.json()
    assert any(h["kind"] == "school" and h["slug"] == "uit" for h in hits)
