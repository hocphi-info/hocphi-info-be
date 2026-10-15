"""scripts/import_school_disclosure.py — nap danh gia muc cong khai hoc phi tu
CSV, khoa theo slug; va field `school.tuitionDisclosure` tren API.

Cung khuon test_import_school_logos.py: `run_seed()` nap 50 truong (commit that),
roi chay `main()` (tu mo SessionLocal + commit that). Fixture `db` TRUNCATE
`schools` o dau moi test nen khong ro ri giua cac test.
"""

import csv
from datetime import date
from pathlib import Path

import pytest
import scripts.import_school_disclosure as mod
from app.enums import TuitionDisclosure
from app.main import app
from app.models import School
from httpx import ASGITransport, AsyncClient
from scripts.import_school_disclosure import main as run_import
from scripts.seed import main as run_seed
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.markers import needs_crawled_seeds

_HEADER = ("slug", "name", "tuition_disclosure", "checked_on", "evidence_url", "note")
_EVIDENCE = "https://example.org/hoc-phi"
_HSU_ROW = (
    "dh-hoa-sen",
    "Hoa Sen",
    "khong_minh_bach",
    "2026-10-16",
    _EVIDENCE,
    "45-85",
)


def _write_csv(path: Path, rows: list[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        writer.writerows(rows)


async def _school(db: AsyncSession, slug: str) -> School:
    school = await db.scalar(select(School).where(School.slug == slug))
    assert school is not None
    await db.refresh(school)  # script ghi qua session khac
    return school


@pytest.fixture
def csv_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "007_school_tuition_disclosure.csv"
    monkeypatch.setattr(mod, "CSV_PATH", path)
    return path


async def test_import_sets_all_columns_by_slug(
    db: AsyncSession, csv_path: Path
) -> None:
    await run_seed()
    _write_csv(
        csv_path,
        [
            _HSU_ROW,
            ("hust", "HUST", "theo_nganh", "2026-10-15", _EVIDENCE, ""),
        ],
    )

    await run_import()

    hsu = await _school(db, "dh-hoa-sen")
    assert hsu.tuition_disclosure == TuitionDisclosure.KHONG_MINH_BACH
    assert hsu.tuition_disclosure_checked_on == date(2026, 10, 16)
    assert hsu.tuition_disclosure_evidence_url == _EVIDENCE
    assert hsu.tuition_disclosure_note == "45-85"
    hust = await _school(db, "hust")
    assert hust.tuition_disclosure == TuitionDisclosure.THEO_NGANH
    assert hust.tuition_disclosure_note is None  # note rong -> NULL
    # Truong khong co trong CSV = chua danh gia.
    assert (await _school(db, "neu")).tuition_disclosure is None


async def test_import_skips_invalid_rows(db: AsyncSession, csv_path: Path) -> None:
    await run_seed()
    _write_csv(
        csv_path,
        [
            ("hust", "HUST", "", "", "", ""),  # chua danh gia -> bo qua
            ("uit", "UIT", "vang", "2026-10-16", _EVIDENCE, ""),  # muc la
            ("ueh", "UEH", "theo_nganh", "16/10/2026", _EVIDENCE, ""),  # ngay sai
            ("neu", "NEU", "theo_nganh", "2026-10-16", "www.neu.edu.vn", ""),  # url
            ("khong-ton-tai", "X", "theo_nganh", "2026-10-16", _EVIDENCE, ""),
        ],
    )

    await run_import()  # khong duoc raise

    for slug in ("hust", "uit", "ueh", "neu"):
        assert (await _school(db, slug)).tuition_disclosure is None


async def test_import_is_idempotent(
    db: AsyncSession, csv_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    await run_seed()
    _write_csv(
        csv_path,
        [("hust", "HUST", "theo_nganh", "2026-10-15", _EVIDENCE, "co bang theo nganh")],
    )

    await run_import()
    capsys.readouterr()
    await run_import()

    assert "cap nhat 0, giu nguyen 1" in capsys.readouterr().out


async def test_import_dry_run_does_not_write(
    db: AsyncSession, csv_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_seed()
    _write_csv(csv_path, [("hust", "HUST", "theo_nganh", "2026-10-15", _EVIDENCE, "")])
    monkeypatch.setattr("sys.argv", ["import_school_disclosure", "--dry-run"])

    await run_import()

    assert (await _school(db, "hust")).tuition_disclosure is None


def _write_bad_header(path: Path) -> None:
    path.write_text("slug,muc\nhust,theo_nganh\n", encoding="utf-8")


async def test_import_bad_header_exits(csv_path: Path) -> None:
    _write_bad_header(csv_path)
    with pytest.raises(SystemExit):
        await run_import()


async def test_check_requires_evidence_when_level_set(db: AsyncSession) -> None:
    await run_seed()
    hust = await _school(db, "hust")
    hust.tuition_disclosure = TuitionDisclosure.THEO_NGANH  # thieu ngay + bang chung
    with pytest.raises(IntegrityError, match="ck_schools_disclosure_evidence"):
        await db.flush()


# /schools/dh-hoa-sen tra 404 khi thieu dh-hoa-sen.jsonl (khong track trong git -> CI).
@needs_crawled_seeds
async def test_api_exposes_tuition_disclosure(db: AsyncSession, csv_path: Path) -> None:
    await run_seed()
    _write_csv(
        csv_path,
        [_HSU_ROW],
    )
    await run_import()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        hsu = (await client.get("/api/v1/schools/dh-hoa-sen")).json()["school"]
        hcmut = (await client.get("/api/v1/schools/dh-bach-khoa-tphcm")).json()[
            "school"
        ]

    assert hsu["tuitionDisclosure"] == {
        "level": "khong_minh_bach",
        "checkedOn": "2026-10-16",
        "evidenceUrl": _EVIDENCE,
        "note": "45-85",
    }
    # Chua danh gia -> key van co mat, gia tri null (hop dong `| null`, khong `?:`).
    assert hcmut["tuitionDisclosure"] is None
