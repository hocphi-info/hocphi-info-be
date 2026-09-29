"""Pytest markers dung chung giua cac file test.

`needs_crawled_seeds`: nhieu test endpoint kiem tra so lieu THAT cua
`seeds/*.jsonl` (output AI-crawler — vd "230 hang", ngay TDTU co 2 co so). Tu
commit 83664dd phan lon file jsonl KHONG con duoc track trong git (.gitignore),
nen o may sach (CI) chung khong co du lieu de doi chieu -> skip, khong fail.
Tren may dev (co du file) test chay day du nhu cu.
"""

import pytest
from scripts.seed import SEEDS_DIR
from scripts.seed_majors_mapping import ROW_TO_MAJOR_SLUG

_missing = sorted(f for f in ROW_TO_MAJOR_SLUG if not (SEEDS_DIR / f).exists())

needs_crawled_seeds = pytest.mark.skipif(
    bool(_missing),
    reason="seeds/*.jsonl khong duoc track trong git — thieu: "
    + ", ".join(_missing[:3]),
)
