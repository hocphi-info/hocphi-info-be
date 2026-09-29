"""Taxonomy nganh (seeds/004..006 + migration 0005).

Cac file CSV/SQL nay CO track trong git nen test chay day du tren CI (khac cac test
dung seeds/*.jsonl — xem tests/markers.py). Hai nhom:

1. Kiem tra file (thuan Python, khong DB): cay hop le, anh xa 143 nganh day du,
   alias khong tro vao nganh khong ton tai.
2. Kiem tra DB (fixture `db`, SAVEPOINT): nap idempotent, rang buoc CHECK/FK cua
   migration 0005 tu choi du lieu sai.
"""

import csv
import re
from collections import Counter
from pathlib import Path

import pytest
from app.models import MajorAlias, TaxonomyNode
from app.text import normalize
from scripts.seed import (
    SEEDS_DIR,
    apply_major_taxonomy,
    load_aliases,
    load_taxonomy,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _csv(name: str) -> list[dict[str, str]]:
    with (SEEDS_DIR / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _major_slugs() -> set[str]:
    sql = (SEEDS_DIR / "002_majors.sql").read_text(encoding="utf-8")
    return set(re.findall(r"^\s*\('([a-z0-9-]+)',", sql, re.M))


# --- 1. Kiem tra file -------------------------------------------------------


def test_taxonomy_csv_is_a_valid_three_level_tree() -> None:
    rows = _csv("004_taxonomy.csv")
    by_code = {r["code"]: r for r in rows}
    assert len(by_code) == len(rows), "trung `code`"

    for r in rows:
        level = int(r["level"])
        assert len(r["code"]) == {1: 3, 2: 5, 3: 7}[level], r
        assert r["code"].isdigit() and r["name"].strip() == r["name"] != "", r
        if level == 1:
            assert r["parent_code"] == "", r
        else:
            parent = by_code[r["parent_code"]]  # KeyError = cha khong ton tai
            assert int(parent["level"]) == level - 1, r
            assert r["code"].startswith(r["parent_code"]), r


def test_taxonomy_csv_node_counts_are_pinned() -> None:
    # TT 09/2022, trinh do dai hoc, sau khi bo cac nhom "Khac" rong (seeds/README.md).
    counts = Counter(int(r["level"]) for r in _csv("004_taxonomy.csv"))
    assert counts == {1: 23, 2: 75, 3: 377}


def test_taxonomy_csv_known_chain() -> None:
    by_code = {r["code"]: r for r in _csv("004_taxonomy.csv")}
    assert by_code["7480201"]["name"] == "Công nghệ thông tin"
    assert by_code["7480201"]["parent_code"] == "74802"
    assert by_code["74802"]["parent_code"] == "748"
    assert by_code["748"]["name"] == "Máy tính và công nghệ thông tin"


def test_major_mapping_covers_every_major_exactly_once() -> None:
    rows = _csv("005_major_taxonomy.csv")
    slugs = [r["major_slug"] for r in rows]
    assert len(slugs) == len(set(slugs)), "trung major_slug"
    assert set(slugs) == _major_slugs(), (
        "005_major_taxonomy.csv phai co dung 1 dong / nganh trong 002_majors.sql "
        "(nganh moi -> them dong; de trong `taxonomy_code` neu chua phan loai)"
    )


def test_major_mapping_codes_are_official_majors_and_blanks_have_a_reason() -> None:
    majors = {r["code"] for r in _csv("004_taxonomy.csv") if r["level"] == "3"}
    for r in _csv("005_major_taxonomy.csv"):
        if r["taxonomy_code"]:
            assert r["taxonomy_code"] in majors, r
        else:
            assert r["note"].strip(), f"Chua phan loai phai co ly do: {r}"


def test_alias_csv_points_at_real_majors_and_has_no_collisions() -> None:
    rows = _csv("006_major_aliases.csv")
    assert {r["major_slug"] for r in rows} <= _major_slugs()
    keys = [(r["major_slug"], normalize(r["alias"])) for r in rows]
    assert len(keys) == len(set(keys)), "alias trung sau khi chuan hoa"
    # 1 alias khong duoc tro toi 2 nganh khac nhau (nhap nhang -> tim ra 2 ket qua).
    owners: dict[str, set[str]] = {}
    for slug, alias in keys:
        owners.setdefault(alias, set()).add(slug)
    assert all(len(v) == 1 for v in owners.values()), owners


# --- 2. Kiem tra DB ---------------------------------------------------------


async def _load_majors(db: AsyncSession) -> None:
    await db.execute(
        text((Path(SEEDS_DIR) / "002_majors.sql").read_text(encoding="utf-8"))
    )


async def test_taxonomy_seed_loads_and_is_idempotent(db: AsyncSession) -> None:
    await _load_majors(db)
    for _ in range(2):  # lan 2 khong duoc nhan doi / loi
        assert await load_taxonomy(db) == 475
        applied, missing = await apply_major_taxonomy(db)
        assert (applied, missing) == (143, [])
        n_alias, alias_missing = await load_aliases(db)
        assert alias_missing == [] and n_alias == len(_csv("006_major_aliases.csv"))

    level_counts = (
        await db.execute(
            select(TaxonomyNode.level, func.count()).group_by(TaxonomyNode.level)
        )
    ).all()
    assert {level: n for level, n in level_counts} == {1: 23, 2: 75, 3: 377}  # noqa: C416
    assert await db.scalar(select(func.count()).select_from(MajorAlias)) == len(
        _csv("006_major_aliases.csv")
    )


async def test_every_classified_major_points_at_a_level_3_node(
    db: AsyncSession,
) -> None:
    await _load_majors(db)
    await load_taxonomy(db)
    await apply_major_taxonomy(db)
    bad = (
        await db.execute(
            text(
                "SELECT m.slug FROM majors m JOIN taxonomy_nodes t ON t.code = m.code "
                "WHERE t.level <> 3"
            )
        )
    ).all()
    assert bad == []
    n_unclassified = await db.scalar(
        text("SELECT count(*) FROM majors WHERE code IS NULL")
    )
    assert n_unclassified == 23


async def test_apply_major_taxonomy_reports_unknown_slug(db: AsyncSession) -> None:
    await load_taxonomy(db)  # khong nap `majors` -> moi slug deu "khong ton tai"
    applied, missing = await apply_major_taxonomy(db)
    assert applied == 0 and len(missing) == 143


@pytest.mark.parametrize(
    ("row", "with_root", "why"),
    [
        ("('748', 2, NULL, 'x')", False, "level 2 phai co cha"),
        ("('7480', 1, NULL, 'x')", False, "do dai ma khong khop level"),
        ("('74801', 2, '999', 'x')", False, "cha khong ton tai (FK)"),
        ("('74901', 2, '748', 'x')", True, "ma con phai bat dau bang ma cha"),
    ],
)
async def test_taxonomy_nodes_reject_invalid_rows(
    db: AsyncSession, row: str, with_root: bool, why: str
) -> None:
    if with_root:
        await db.execute(
            text("INSERT INTO taxonomy_nodes VALUES ('748', 1, NULL, 'root')")
        )
    with pytest.raises((IntegrityError, DBAPIError)):
        async with db.begin_nested():
            await db.execute(
                text(
                    "INSERT INTO taxonomy_nodes (code, level, parent_code, name) "
                    f"VALUES {row}"
                )
            )
    del why  # chi de doc trong bang tham so


async def test_major_code_must_exist_in_taxonomy(db: AsyncSession) -> None:
    await _load_majors(db)
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(
                text("UPDATE majors SET code = '0000000' WHERE slug = 'ke-toan'")
            )
