"""Buoc 5 — kiem tra file JSONL truoc khi cho vao seeds/.

    uv run python -m crawler.validate seeds/uit.jsonl

Chay duoc doc lap, KHONG can DB — doi chieu school_slug voi seeds/001_schools.sql.
Tra ve exit code 1 neu co dong hong; dong `needs_review` khong phai loi, chi la
hang cho nguoi duyet.

Day la cong kiem soat duy nhat giua "may de xuat" va "du lieu that". Moi thu
o day deu la code tat dinh — khong hoi lai AI de xac nhan cong viec cua AI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from app import enums
from pydantic import ValidationError

from crawler.schema import DEFAULT_CREDITS_PER_YEAR, TuitionRow

REPO = Path(__file__).parent.parent
SCHOOLS_SQL = REPO / "seeds" / "001_schools.sql"

_SLUG_RE = re.compile(r"^\s*\('([a-z0-9-]+)'", re.M)


def doc_slug_hop_le() -> set[str]:
    """Rut slug truong tu seeds/001_schools.sql — nguon su that, khong can DB."""
    if not SCHOOLS_SQL.exists():
        return set()
    return set(_SLUG_RE.findall(SCHOOLS_SQL.read_text(encoding="utf-8")))


def kiem_tra(path: Path) -> int:
    slug_hop_le = doc_slug_hop_le()
    loi: list[str] = []
    rows: list[TuitionRow] = []

    for so_dong, dong in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not dong.strip():
            continue
        try:
            rows.append(TuitionRow.model_validate_json(dong))
        except ValidationError as e:
            for err in e.errors():
                cho = ".".join(str(x) for x in err["loc"]) or "(dong)"
                loi.append(f"  dong {so_dong} · {cho}: {err['msg']}")
        except json.JSONDecodeError as e:
            loi.append(f"  dong {so_dong}: JSON hong — {e}")

    # Slug truong khong co trong danh sach 50 truong pilot.
    if slug_hop_le:
        for i, r in enumerate(rows, 1):
            if r.school_slug not in slug_hop_le:
                loi.append(
                    f"  dong {i}: school_slug {r.school_slug!r} "
                    f"khong co trong seeds/001_schools.sql"
                )

    # Don gia tin chi + so tin chi GIA DINH => con so/nam la BIA. Gap that o UIT
    # 2025-2026: ban CLC co 3 muc/tin chi khac nhau tuy loai mon (1.15tr mon chung,
    # 1.3tr day tieng Viet, 1.5tr day tieng Anh) — khong muc nao nhan 30 ra duoc
    # hoc phi/nam that. Thieu du lieu con hon du lieu sai.
    for i, r in enumerate(rows, 1):
        if (
            r.unit_original is enums.TuitionUnit.DONG_TIN_CHI
            and r.credits_per_year_assumed == DEFAULT_CREDITS_PER_YEAR
        ):
            loi.append(
                f"  dong {i} ({r.major_name_raw}): don gia tin chi nhan voi so tin chi "
                f"MAC DINH ({DEFAULT_CREDITS_PER_YEAR}) => amount_per_year la so bia. "
                f"Chi giu neu tai lieu ghi RO tong tin chi/nam; neu khong thi bo dong."
            )

    # Trung khoa nghiep vu — DB co UNIQUE (program, academic_year), bat som o day.
    khoa = Counter(
        (
            r.school_slug,
            r.major_name_raw,
            r.track,
            r.language,
            r.campus,
            r.academic_year,
        )
        for r in rows
    )
    for k, n in khoa.items():
        if n > 1:
            loi.append(f"  trung {n} dong cho cung 1 chuong trinh + nam hoc: {k}")

    _in_bao_cao(path, rows, loi)
    return 1 if loi else 0


def _in_bao_cao(path: Path, rows: list[TuitionRow], loi: list[str]) -> None:
    print(f"{path}: {len(rows)} dong hop le")

    if rows:
        can_duyet = [r for r in rows if r.needs_review]
        tien = sorted(r.amount_per_year for r in rows)
        print(f"  hoc phi: {tien[0]:,} .. {tien[-1]:,} dong/nam")
        print(f"  nam hoc: {', '.join(sorted({r.academic_year for r in rows}))}")
        print(f"  he    : {', '.join(sorted({r.track.value for r in rows}))}")
        print(f"  cho nguoi duyet: {len(can_duyet)}/{len(rows)} dong")
        for r in can_duyet:
            print(f"    - {r.major_name_raw} ({r.track.value}): {r.review_reason}")

    if loi:
        print(f"\n{len(loi)} LOI — khong duoc dua vao seeds/:", file=sys.stderr)
        for m in loi:
            print(m, file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path)
    args = ap.parse_args()
    if not args.path.exists():
        raise SystemExit(f"Khong thay {args.path}")
    raise SystemExit(kiem_tra(args.path))


if __name__ == "__main__":
    main()
