"""GET /api/schools/{school_slug}/majors/{major_slug} (S3) — httpx.AsyncClient goi
thang app qua ASGITransport, dung chung DB test voi fixture `db` (xem
tests/conftest.py). Response phai dung camelCase, khop pattern
tests/test_majors_endpoint.py.
"""

from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import main as run_seed
from sqlalchemy.ext.asyncio import AsyncSession


async def test_get_program_detail_404_when_school_not_found(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/khong-ton-tai/majors/ke-toan")
    assert resp.status_code == 404


async def test_get_program_detail_404_when_no_program_seeded(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # uit + duoc-hoc: ca 2 ton tai rieng biet nhung khong ghep thanh 1 program.
        resp = await client.get("/api/schools/uit/majors/duoc-hoc")
    assert resp.status_code == 404


async def test_get_program_detail_standard_years_4(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/tdtu/majors/ke-toan")

    assert resp.status_code == 200
    body = resp.json()
    assert body["school"]["slug"] == "tdtu"
    assert "logoUrl" in body["school"]  # co mat trong hop dong (NULL truoc import)
    assert body["major"]["slug"] == "ke-toan"
    assert body["major"]["standardYears"] == 4

    program = next(p for p in body["programs"] if p["program"]["track"] == "dai_tra")
    amounts = program["yearlyAmounts"]
    assert len(amounts) == 4
    assert amounts[0]["academicYear"] == "2026-2027"
    assert amounts[0]["amountPerYear"] == 31_260_000
    assert amounts[0]["isProjected"] is False
    # +10%/nam (app_settings.default_increase_pct — chua seed program_increase).
    assert amounts[1]["amountPerYear"] == 34_386_000
    assert amounts[1]["isProjected"] is True
    assert amounts[3]["isProjected"] is True

    assert program["totalCourse"] == sum(a["amountPerYear"] for a in amounts)
    assert program["totalCourse"] == 145_077_660
    # post_grad_requirements rong o Tuan 3 -> luon bang totalCourse.
    assert program["totalWithLicense"] == program["totalCourse"]
    assert program["increase"] is None


async def test_get_program_detail_standard_years_6_duoc_hoc(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/tdtu/majors/duoc-hoc")

    assert resp.status_code == 200
    body = resp.json()
    assert body["major"]["standardYears"] == 6

    program = body["programs"][0]
    amounts = program["yearlyAmounts"]
    assert len(amounts) == 6
    assert amounts[0]["amountPerYear"] == 68_460_000
    assert amounts[0]["isProjected"] is False
    assert all(a["isProjected"] for a in amounts[1:])
    assert program["totalCourse"] == sum(a["amountPerYear"] for a in amounts)
    assert program["totalWithLicense"] == program["totalCourse"]


async def test_get_program_detail_year1_has_source(db: AsyncSession) -> None:
    """F12 — seed.py gan source_id tu source_url trong jsonl (Tuan 4)."""
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/schools/tdtu/majors/ke-toan")

    assert resp.status_code == 200
    program = resp.json()["programs"][0]
    source = program["year1"]["source"]
    assert source is not None
    assert source["url"].startswith("http")
    assert source["docType"]
    # Nam du phong (Nam 2..N) la so tinh, khong co source rieng — chi Nam 1
    # (TuitionRecordOut) moi co field nay; yearlyAmounts khong co "source".
    assert "source" not in program["yearlyAmounts"][1]


async def test_get_program_detail_orders_multiple_tracks(db: AsyncSession) -> None:
    await run_seed()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # tdtu/ngon-ngu-anh co 2 program: tien_tien va chat_luong_cao.
        resp = await client.get("/api/schools/tdtu/majors/ngon-ngu-anh")

    assert resp.status_code == 200
    tracks = [p["program"]["track"] for p in resp.json()["programs"]]
    assert len(tracks) == 2
    assert set(tracks) == {"tien_tien", "chat_luong_cao"}
