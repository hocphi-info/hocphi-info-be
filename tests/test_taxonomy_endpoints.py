"""API phan loai nganh: `major.taxonomy` / `aliases`, `relatedMajors`, `byField`,
`?search=` theo alias. Du lieu test: tests/factories.py (khong dung jsonl).
"""

from app.main import app
from app.text import alias_matches
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import PROGRAMS, seed_minimal


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _major_of(rows: list[dict], slug: str) -> dict:
    return next(r["major"] for r in rows if r["major"]["slug"] == slug)


# --- /api/v1/majors ---------------------------------------------------------


async def test_majors_expose_taxonomy_and_aliases(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        rows = (await client.get("/api/v1/majors")).json()

    khmt = _major_of(rows, "khoa-hoc-may-tinh")
    assert khmt["code"] == "7480101"
    assert khmt["taxonomy"] == {
        "field": {"code": "748", "name": "Máy tính và công nghệ thông tin"},
        "group": {"code": "74801", "name": "Máy tính"},
    }
    assert khmt["aliases"] == ["computer science", "cs", "khmt"]
    assert "groupCode" not in khmt  # 6 nhom tu dat cu da bi bo (migration 0006)

    art = _major_of(rows, "digital-art")
    assert art["code"] is None and art["taxonomy"] is None and art["aliases"] == []


async def test_majors_before_taxonomy_is_seeded_still_ok(db: AsyncSession) -> None:
    # Kich ban rollout: image moi da chay nhung `scripts.seed` chua nap taxonomy.
    await seed_minimal(with_taxonomy=False)
    async with _client() as client:
        resp = await client.get("/api/v1/majors")
        coverage = (await client.get("/api/v1/coverage")).json()

    assert resp.status_code == 200
    majors = [r["major"] for r in resp.json()]
    assert majors and all(m["taxonomy"] is None and m["aliases"] == [] for m in majors)
    assert coverage["byField"] == [
        {
            "fieldCode": None,
            "fieldName": "Chưa phân loại",
            "programsWithTuition": len(PROGRAMS),
        }
    ]


async def test_search_matches_aliases_by_equality_or_prefix(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:

        async def slugs(q: str) -> set[str]:
            rows = (await client.get("/api/v1/majors", params={"search": q})).json()
            return {r["major"]["slug"] for r in rows}

        assert await slugs("cntt") == {
            "cong-nghe-thong-tin"
        }  # alias, khong co trong ten
        assert await slugs("KHMT") == {
            "khoa-hoc-may-tinh"
        }  # khong phan biet hoa/thuong
        assert await slugs("khm") == {"khoa-hoc-may-tinh"}  # tien to >= 3 ky tu
        assert await slugs("computer science") == {"khoa-hoc-may-tinh"}
        # alias "it" cua CNTT khop bang han; ten "Digital Art" van khop vi ten chua
        # "it" (hanh vi cu khong doi) — alias KHONG them ket qua nao khac.
        assert "cong-nghe-thong-tin" in await slugs("it")


def test_alias_matches_rule() -> None:
    assert alias_matches("it", "it")
    assert not alias_matches("it", "itxyz")  # < 3 ky tu: chi khop bang
    assert alias_matches("khm", "khmt")
    assert not alias_matches("mt", "khmt")  # khong khop chuoi con
    assert not alias_matches("digital", "it")


# --- chi tiet nganh: relatedMajors -----------------------------------------


async def test_related_majors_same_group_dai_tra_only(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        detail = (
            await client.get("/api/v1/schools/truong-a/majors/khoa-hoc-may-tinh")
        ).json()

    # Cung nhom 74801 (Máy tính): KTPM co o 2 truong (dai tra 32tr, 44tr; he CLC 90tr
    # KHONG tinh). Tri tue nhan tao chi co he CLC -> khong xuat hien. CNTT (74802) khac
    # nhom -> khong xuat hien. Chinh KHMT bi loai.
    assert detail["relatedMajors"] == [
        {
            "slug": "ky-thuat-phan-mem",
            "name": "Kỹ thuật phần mềm",
            "nSchools": 2,
            "minYear1Amount": 32_000_000,
            "maxYear1Amount": 44_000_000,
        }
    ]
    assert detail["major"]["taxonomy"]["group"]["code"] == "74801"


async def test_related_majors_empty_for_unclassified_major(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        detail = (
            await client.get("/api/v1/schools/truong-a/majors/digital-art")
        ).json()
    assert detail["relatedMajors"] == []
    assert detail["major"]["taxonomy"] is None


async def test_school_detail_majors_carry_taxonomy(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        detail = (await client.get("/api/v1/schools/truong-a")).json()
    by_slug = {p["major"]["slug"]: p["major"] for p in detail["programs"]}
    assert by_slug["cong-nghe-thong-tin"]["taxonomy"]["group"]["code"] == "74802"
    assert by_slug["digital-art"]["taxonomy"] is None


# --- coverage.byField -------------------------------------------------------


async def test_coverage_by_field_counts_and_reconciles(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        body = (await client.get("/api/v1/coverage")).json()

    assert body["byField"] == [
        {
            "fieldCode": "748",
            "fieldName": "Máy tính và công nghệ thông tin",
            "programsWithTuition": len(PROGRAMS) - 1,
        },
        {
            "fieldCode": None,
            "fieldName": "Chưa phân loại",
            "programsWithTuition": 1,
        },
    ]
    # Bat bien cua coverage: cac phep dem dung chung 1 CTE `pub` nen tong khop nhau.
    total = sum(r["programsWithTuition"] for r in body["byField"])
    assert total == body["totals"]["programsWithTuition"]
    assert total == sum(s["nPrograms"] for s in body["schools"])


async def test_coverage_by_field_empty_db(db: AsyncSession) -> None:
    async with _client() as client:
        body = (await client.get("/api/v1/coverage")).json()
    assert body["byField"] == []
