"""GET /api/v1/taxonomy, /api/v1/taxonomy/{code}: duong dan (de quy LEN), hau due
(de quy XUONG), nhanh khong du lieu bi loai, khoang hoc phi chi he dai tra.

Du lieu: tests/factories.py (khong dung jsonl). Cay mong doi (xem PROGRAMS):
  748 -> 74801 -> {7480101 KHMT (2 CT), 7480103 KTPM (3 CT), 7480107 AI (1 CT, chi CLC)}
      -> 74802 -> {7480201 CNTT (1 CT)};  + 1 CT nganh chua phan loai (digital-art).
"""

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient
from scripts.seed import load_taxonomy
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import PROGRAMS, seed_minimal


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_roots_list_fields_with_data_and_unclassified(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        body = (await client.get("/api/v1/taxonomy")).json()

    assert body["fields"] == [
        {
            "code": "748",
            "name": "Máy tính và công nghệ thông tin",
            "level": 1,
            "nMajors": 4,
            "nPrograms": len(PROGRAMS) - 1,
        }
    ]
    assert body["unclassified"] == {"nMajors": 1, "nPrograms": 1}


async def test_field_node_has_path_children_and_majors(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        body = (await client.get("/api/v1/taxonomy/748")).json()

    assert [n["code"] for n in body["path"]] == ["748"]
    assert (body["nMajors"], body["nPrograms"]) == (4, 7)
    # Con truc tiep, sap theo so chuong trinh giam dan; so gop tu hau due.
    assert [
        (c["code"], c["level"], c["nMajors"], c["nPrograms"]) for c in body["children"]
    ] == [
        ("74801", 2, 3, 6),
        ("74802", 2, 1, 1),
    ]
    majors = {m["slug"]: m for m in body["majors"]}
    assert set(majors) == {
        "khoa-hoc-may-tinh",
        "ky-thuat-phan-mem",
        "tri-tue-nhan-tao",
        "cong-nghe-thong-tin",
    }
    assert majors["khoa-hoc-may-tinh"]["nSchools"] == 2
    # He CLC (90tr) KHONG tinh vao khoang; chi 32tr..44tr cua he dai tra.
    assert (
        majors["ky-thuat-phan-mem"]["minYear1Amount"],
        majors["ky-thuat-phan-mem"]["maxYear1Amount"],
    ) == (32_000_000, 44_000_000)
    # Nganh chi co he CLC: van co mat, nhung khong co khoang dai tra.
    assert majors["tri-tue-nhan-tao"]["minYear1Amount"] is None
    assert majors["tri-tue-nhan-tao"]["maxYear1Amount"] is None


async def test_group_and_major_nodes_walk_the_tree(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        group = (await client.get("/api/v1/taxonomy/74801")).json()
        leaf = (await client.get("/api/v1/taxonomy/7480101")).json()

    assert [n["code"] for n in group["path"]] == ["748", "74801"]
    assert {c["code"]: c["nPrograms"] for c in group["children"]} == {
        "7480101": 2,
        "7480103": 3,
        "7480107": 1,
    }
    # Sap theo so truong giam dan roi ten: KHMT va KTPM deu 2 truong -> theo ten.
    assert [m["slug"] for m in group["majors"]] == [
        "khoa-hoc-may-tinh",
        "ky-thuat-phan-mem",
        "tri-tue-nhan-tao",
    ]

    assert [n["code"] for n in leaf["path"]] == ["748", "74801", "7480101"]
    assert leaf["children"] == []
    assert [m["slug"] for m in leaf["majors"]] == ["khoa-hoc-may-tinh"]
    assert leaf["level"] == 3 and leaf["name"] == "Khoa học máy tính"


async def test_children_sums_reconcile_with_parent(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        for code in ("748", "74801", "74802"):
            body = (await client.get(f"/api/v1/taxonomy/{code}")).json()
            assert sum(c["nPrograms"] for c in body["children"]) == body["nPrograms"]
            assert sum(c["nMajors"] for c in body["children"]) == body["nMajors"]


async def test_unclassified_node(db: AsyncSession) -> None:
    await seed_minimal()
    async with _client() as client:
        body = (await client.get("/api/v1/taxonomy/unclassified")).json()

    assert body["code"] == "unclassified" and body["level"] == 0
    assert body["name"] == "Chưa phân loại"
    assert body["path"] == [] and body["children"] == []
    assert [m["slug"] for m in body["majors"]] == ["digital-art"]
    assert (body["nMajors"], body["nPrograms"]) == (1, 1)


@pytest.mark.parametrize("code", ["999", "7480999", "abc", "7480", "74801x", "748-1"])
async def test_unknown_or_malformed_code_is_404(db: AsyncSession, code: str) -> None:
    await seed_minimal()
    async with _client() as client:
        resp = await client.get(f"/api/v1/taxonomy/{code}")
    assert resp.status_code == 404


async def test_taxonomy_loaded_but_no_tuition_data_is_empty_not_error(
    db: AsyncSession,
) -> None:
    from app.db import SessionLocal

    async with SessionLocal() as s:
        await load_taxonomy(s)
        await s.commit()
    async with _client() as client:
        roots = (await client.get("/api/v1/taxonomy")).json()
        node = (await client.get("/api/v1/taxonomy/748")).json()

    assert roots == {"fields": [], "unclassified": None}
    assert node["nPrograms"] == 0 and node["majors"] == [] and node["children"] == []
    assert [n["code"] for n in node["path"]] == ["748"]


async def test_empty_db_returns_empty_roots(db: AsyncSession) -> None:
    async with _client() as client:
        resp = await client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    assert resp.json() == {"fields": [], "unclassified": None}
