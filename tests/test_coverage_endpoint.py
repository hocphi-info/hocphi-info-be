"""GET /api/coverage — httpx.AsyncClient goi thang app qua ASGITransport, dung
chung DB test voi fixture `db` (xem tests/conftest.py). Response phai dung
camelCase, khop hop dong trong docs/plans/2026-09-06-001-...-plan.md va nhom
`Coverage*` cua hocphi-info-fe/src/types/domain.ts.

3 nhom test: (1) DB rong -> shape zero, khong 500; (2) da seed -> so khop DB
that; (3) bat bien reconcile (cac so cong khop nhau vi cung 1 CTE `pub`).
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession

MAJOR_GROUP_CODES = {"CNTT", "KINH_TE", "KY_THUAT", "LOGISTICS", "LUAT", "Y_DUOC"}


async def test_coverage_empty_db_returns_zero_shape(db: AsyncSession) -> None:
    # Khong goi run_seed(): schools/programs/tuition rong; cities + major_groups
    # van co (seed trong migration 0001, khong bi TRUNCATE boi fixture `db`).
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coverage")

    assert resp.status_code == 200
    body = resp.json()

    assert body["snapshotDate"] is None
    assert body["totals"] == {
        "schoolsTotal": 0,
        "schoolsWithData": 0,
        "programsWithTuition": 0,
        "tuitionRecords": 0,
        "sourcesCited": 0,
    }
    assert body["schools"] == []
    # cities LEFT JOIN -> van co 2 dong, moi so = 0.
    assert {r["cityCode"] for r in body["byCity"]} == {"HCM", "HN"}
    assert all(
        r["schoolsTotal"] == 0 and r["schoolsWithData"] == 0 for r in body["byCity"]
    )
    # major_groups LEFT JOIN -> ca 6 nhom, programsWithTuition = 0.
    assert {r["groupCode"] for r in body["byMajorGroup"]} == MAJOR_GROUP_CODES
    assert all(r["programsWithTuition"] == 0 for r in body["byMajorGroup"])
    # Khong co truong nao -> khong nhom category nao.
    assert body["byCategory"] == []


async def test_coverage_seeded_totals_match_db(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coverage")

    assert resp.status_code == 200
    body = resp.json()

    assert body["totals"] == {
        "schoolsTotal": 50,
        "schoolsWithData": 10,
        "programsWithTuition": 150,
        "tuitionRecords": 150,
        "sourcesCited": 11,
    }
    # snapshotDate = max(tuition_records.updated_at)::date -> chuoi "YYYY-MM-DD".
    assert isinstance(body["snapshotDate"], str)
    assert len(body["snapshotDate"]) == 10

    by_city = {r["cityCode"]: r for r in body["byCity"]}
    assert by_city["HCM"] == {
        "cityCode": "HCM",
        "cityName": "TP. Ho Chi Minh",
        "schoolsTotal": 25,
        "schoolsWithData": 8,
    }
    assert by_city["HN"]["schoolsTotal"] == 25
    assert by_city["HN"]["schoolsWithData"] == 2

    by_group = {r["groupCode"]: r["programsWithTuition"] for r in body["byMajorGroup"]}
    assert by_group.keys() == MAJOR_GROUP_CODES
    assert by_group["KINH_TE"] == 52
    assert by_group["KY_THUAT"] == 52
    assert sum(by_group.values()) == 150


async def test_coverage_seeded_schools_rows_shape(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coverage")

    body = resp.json()
    schools = body["schools"]
    assert len(schools) == 50  # TAT CA truong con song, ke ca nPrograms = 0

    # Sort nPrograms desc -> HUTECH dau bang.
    top = schools[0]
    assert top["slug"] == "hutech"
    assert top["nPrograms"] == 64
    assert top["latestSourceDocType"] == "thong_bao_hoc_phi"
    assert set(top.keys()) == {
        "slug",
        "name",
        "shortName",
        "cityCode",
        "category",
        "nPrograms",
        "latestSourceDocType",
        "latestSourceDate",
        "lastUpdated",
    }

    # Truong trong hang doi: nPrograms = 0, khong co nguon.
    queued = [s for s in schools if s["nPrograms"] == 0]
    assert queued, "phai co truong pilot chua seed chuong trinh nao"
    assert all(s["latestSourceDocType"] is None for s in queued)
    assert all(s["lastUpdated"] is None for s in queued)


async def test_coverage_seeded_numbers_reconcile(db: AsyncSession) -> None:
    """Moi phep dem bat nguon tu 1 CTE `pub` -> cac tong cong khop nhau."""
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/coverage")

    body = resp.json()
    totals = body["totals"]

    assert (
        sum(r["schoolsWithData"] for r in body["byCity"]) == totals["schoolsWithData"]
    )
    assert (
        sum(r["schoolsWithData"] for r in body["byCategory"])
        == totals["schoolsWithData"]
    )
    assert (
        sum(r["programsWithTuition"] for r in body["byMajorGroup"])
        == totals["programsWithTuition"]
    )
    assert (
        sum(s["nPrograms"] for s in body["schools"]) == totals["programsWithTuition"]
    )
    assert sum(r["schoolsTotal"] for r in body["byCity"]) == totals["schoolsTotal"]
    assert len(body["schools"]) == totals["schoolsTotal"]
