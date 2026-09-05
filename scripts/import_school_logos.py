"""Nap logo_url cho `schools` tu seeds/003_school_logos.csv (owner tu tao).

    uv run python -m scripts.import_school_logos [--dry-run]

Khac `scripts/seed.py` (nap moi du lieu): script nay chi UPDATE 1 cot `logo_url`
cua ban ghi da co, khoa theo `slug`. Idempotent — chay lai nhieu lan cho cung
ket qua (dong da dung URL -> nhanh "giu nguyen"). KHONG tao row moi; slug la chi
in canh bao, khong lam script fail.

File CSV (hop dong — xem docs/plans/2026-09-05-001-...-plan.md § Hop dong file CSV):
- Duong dan co dinh: seeds/003_school_logos.csv
- Header bat buoc: slug,name,short_name,logo_url  (dung thu tu cot nhu bang schools)
- Khoa join = `slug`. `name`/`short_name` chi de owner nhin, script khong doc.
- `logo_url` rong -> bo qua dong do (dem vao "rong").
- `logo_url` hop le -> bat dau bang http:// , https:// hoac / (duong dan trong
  hocphi-info-fe/public/).

Bam khuon scripts/seed.py: tu mo `SessionLocal()` (khong qua Depends — day khong
phai HTTP request), chay `text()`, commit 1 lan o cuoi.
"""

import asyncio
import csv
import sys
from pathlib import Path

from app.db import SessionLocal, engine
from sqlalchemy import text

CSV_PATH = Path(__file__).resolve().parent.parent / "seeds" / "003_school_logos.csv"
REQUIRED_COLUMNS = ("slug", "name", "short_name", "logo_url")
VALID_URL_PREFIXES = ("http://", "https://", "/")


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
        print(
            f"Header thieu cot {missing}. Can du: {','.join(REQUIRED_COLUMNS)}"
        )
        sys.exit(1)

    updated = unchanged = skipped_empty = bad_url = not_found = 0

    async with SessionLocal() as session:
        for line_no, row in enumerate(rows, start=2):  # dong 1 la header
            slug = (row.get("slug") or "").strip()
            url = (row.get("logo_url") or "").strip()

            if not slug:
                print(f"  [bo qua] dong {line_no}: thieu slug")
                continue
            if not url:
                skipped_empty += 1
                continue
            if not url.startswith(VALID_URL_PREFIXES):
                print(
                    f"  [bo qua] dong {line_no} {slug!r}: "
                    f"logo_url khong hop le: {url!r}"
                )
                bad_url += 1
                continue

            # 1 query phan biet "khong co truong" vs "truong co logo_url = NULL":
            # .first() tra Row hoac None; Row.logo_url la gia tri hien tai.
            current_row = (
                await session.execute(
                    text(
                        "SELECT logo_url FROM schools "
                        "WHERE slug = :slug AND deleted_at IS NULL"
                    ),
                    {"slug": slug},
                )
            ).first()

            if current_row is None:
                print(f"  [khong thay] dong {line_no}: slug {slug!r} khong co trong DB")
                not_found += 1
                continue
            if current_row.logo_url == url:
                unchanged += 1
                continue

            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE schools SET logo_url = :url, updated_at = now() "
                        "WHERE slug = :slug AND deleted_at IS NULL"
                    ),
                    {"url": url, "slug": slug},
                )
            updated += 1

        if not dry_run:
            await session.commit()

    tag = "[DRY-RUN] " if dry_run else ""
    print(
        f"{tag}cap nhat {updated}, giu nguyen {unchanged}, "
        f"rong {skipped_empty}, url la {bad_url}, khong thay slug {not_found}"
    )
    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
