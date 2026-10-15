"""Nap danh gia muc cong khai hoc phi cho `schools` tu
seeds/007_school_tuition_disclosure.csv (owner tu danh gia tung truong).

    uv run python -m scripts.import_school_disclosure [--dry-run]

Cung khuon scripts/import_school_logos.py: chi UPDATE ban ghi da co, khoa theo
`slug`, idempotent, slug la chi canh bao. Khac logo: 1 dong ghi 4 cot cung luc
(muc + ngay kiem tra + link bang chung + ghi chu) va CHECK
ck_schools_disclosure_evidence bat buoc co ngay + bang chung khi co muc.

File CSV:
- Header bat buoc: slug,name,tuition_disclosure,checked_on,evidence_url,note
- `name` chi de owner nhin, script khong doc.
- `tuition_disclosure` rong -> bo qua dong (chua danh gia). Hop le:
  theo_nganh (xanh) | khong_minh_bach (do).
- `checked_on` dang YYYY-MM-DD; `evidence_url` bat dau bang http:// hoac https://.
- `note` tuy chon — viet theo kieu su kien, FE hien nguyen van.
"""

import asyncio
import csv
import sys
from datetime import date
from pathlib import Path

from app.db import SessionLocal, engine
from app.enums import TuitionDisclosure
from sqlalchemy import text

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
CSV_PATH = SEEDS_DIR / "007_school_tuition_disclosure.csv"
REQUIRED_COLUMNS = (
    "slug",
    "name",
    "tuition_disclosure",
    "checked_on",
    "evidence_url",
    "note",
)
VALID_URL_PREFIXES = ("http://", "https://")
VALID_LEVELS = {level.value for level in TuitionDisclosure}


def _parse_row(
    line_no: int, row: dict[str, str]
) -> tuple[str, date, str, str | None] | None:
    """Tra (level, checked_on, evidence_url, note) hoac None neu dong loi."""
    slug = row["slug"]
    level = (row.get("tuition_disclosure") or "").strip()
    url = (row.get("evidence_url") or "").strip()
    note = (row.get("note") or "").strip() or None

    if level not in VALID_LEVELS:
        print(f"  [bo qua] dong {line_no} {slug!r}: muc la {level!r}")
        return None
    try:
        checked_on = date.fromisoformat((row.get("checked_on") or "").strip())
    except ValueError:
        print(f"  [bo qua] dong {line_no} {slug!r}: checked_on phai dang YYYY-MM-DD")
        return None
    if not url.startswith(VALID_URL_PREFIXES):
        print(f"  [bo qua] dong {line_no} {slug!r}: evidence_url khong hop le")
        return None
    return level, checked_on, url, note


async def main() -> None:
    dry_run = "--dry-run" in sys.argv[1:]

    if not CSV_PATH.exists():
        print(
            f"Khong thay {CSV_PATH}.\n"
            f"Tao file CSV UTF-8 voi header: {','.join(REQUIRED_COLUMNS)}"
        )
        sys.exit(1)

    # utf-8-sig: tu bo BOM neu Excel them; file khong co BOM cung doc binh thuong.
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        print(f"Header thieu cot {missing}. Can du: {','.join(REQUIRED_COLUMNS)}")
        sys.exit(1)

    updated = unchanged = skipped_empty = invalid = not_found = 0

    async with SessionLocal() as session:
        for line_no, row in enumerate(rows, start=2):  # dong 1 la header
            slug = row["slug"] = (row.get("slug") or "").strip()
            if not slug:
                print(f"  [bo qua] dong {line_no}: thieu slug")
                continue
            if not (row.get("tuition_disclosure") or "").strip():
                skipped_empty += 1
                continue
            parsed = _parse_row(line_no, row)
            if parsed is None:
                invalid += 1
                continue
            level, checked_on, url, note = parsed

            current = (
                await session.execute(
                    text(
                        "SELECT tuition_disclosure, tuition_disclosure_checked_on, "
                        "tuition_disclosure_evidence_url, tuition_disclosure_note "
                        "FROM schools WHERE slug = :slug AND deleted_at IS NULL"
                    ),
                    {"slug": slug},
                )
            ).first()

            if current is None:
                print(f"  [khong thay] dong {line_no}: slug {slug!r} khong co trong DB")
                not_found += 1
                continue
            if tuple(current) == (level, checked_on, url, note):
                unchanged += 1
                continue

            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE schools SET "
                        "tuition_disclosure = CAST(:level AS tuition_disclosure), "
                        "tuition_disclosure_checked_on = :checked_on, "
                        "tuition_disclosure_evidence_url = :url, "
                        "tuition_disclosure_note = :note, updated_at = now() "
                        "WHERE slug = :slug AND deleted_at IS NULL"
                    ),
                    {
                        "level": level,
                        "checked_on": checked_on,
                        "url": url,
                        "note": note,
                        "slug": slug,
                    },
                )
            updated += 1

        if not dry_run:
            await session.commit()

    tag = "[DRY-RUN] " if dry_run else ""
    print(
        f"{tag}cap nhat {updated}, giu nguyen {unchanged}, "
        f"rong {skipped_empty}, loi {invalid}, khong thay slug {not_found}"
    )
    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
