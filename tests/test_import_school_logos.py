"""scripts/import_school_logos.py — nap logo_url tu CSV, khoa theo slug.

Cung khuon test_seed.py: `run_seed()` nap 50 truong (commit that vao DB test),
roi chay `import_school_logos.main()` (cung tu mo SessionLocal + commit that).
Fixture `db` TRUNCATE `schools` o dau moi test nen khong ro ri giua cac test.
"""

import csv
from pathlib import Path

import pytest
import scripts.import_school_logos as mod
from app.models import School
from scripts.import_school_logos import main as run_import
from scripts.seed import main as run_seed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_HEADER = ("slug", "name", "short_name", "logo_url")


def _write_csv(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        writer.writerows(rows)


async def _logo_of(db: AsyncSession, slug: str) -> str | None:
    return await db.scalar(select(School.logo_url).where(School.slug == slug))


async def test_import_sets_logo_url_by_slug(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_seed()
    csv_path = tmp_path / "003_school_logos.csv"
    _write_csv(
        csv_path,
        [
            ("hust", "DH Bach Khoa Ha Noi", "HUST", "https://example.org/hust.png"),
            ("uit", "DH CNTT", "UIT", "/logos/uit.svg"),
        ],
    )
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)

    await run_import()

    assert await _logo_of(db, "hust") == "https://example.org/hust.png"
    assert await _logo_of(db, "uit") == "/logos/uit.svg"
    # Truong khong co trong CSV giu nguyen NULL.
    assert await _logo_of(db, "neu") is None


async def test_import_skips_empty_url_and_unknown_slug(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_seed()
    csv_path = tmp_path / "003_school_logos.csv"
    _write_csv(
        csv_path,
        [
            ("hust", "DH Bach Khoa Ha Noi", "HUST", ""),  # rong -> bo qua
            ("khong-ton-tai", "Truong ma", "X", "https://example.org/x.png"),
            ("ueh", "DH Kinh te TPHCM", "UEH", "ftp://example.org/ueh.png"),  # url la
        ],
    )
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)

    await run_import()  # khong duoc raise

    assert await _logo_of(db, "hust") is None
    assert await _logo_of(db, "ueh") is None


async def test_import_is_idempotent(
    db: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await run_seed()
    csv_path = tmp_path / "003_school_logos.csv"
    _write_csv(
        csv_path,
        [("hust", "DH Bach Khoa Ha Noi", "HUST", "https://example.org/hust.png")],
    )
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)

    await run_import()
    capsys.readouterr()
    await run_import()

    assert "cap nhat 0" in capsys.readouterr().out
    assert await _logo_of(db, "hust") == "https://example.org/hust.png"


async def test_import_dry_run_does_not_write(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_seed()
    csv_path = tmp_path / "003_school_logos.csv"
    _write_csv(
        csv_path,
        [("hust", "DH Bach Khoa Ha Noi", "HUST", "https://example.org/hust.png")],
    )
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)
    monkeypatch.setattr("sys.argv", ["import_school_logos", "--dry-run"])

    await run_import()

    assert await _logo_of(db, "hust") is None


async def test_import_missing_file_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "CSV_PATH", tmp_path / "khong-co.csv")
    with pytest.raises(SystemExit):
        await run_import()


async def test_import_bad_header_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "003_school_logos.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("slug,logo\nhust,https://example.org/x.png\n")
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)
    with pytest.raises(SystemExit):
        await run_import()
