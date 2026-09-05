"""Chuan hoa chuoi tim kiem — bo dau tieng Viet + lowercase.

Truoc day song trong `app/search.py` (endpoint GET /api/search rieng). Endpoint
do da bo; `search` gio la query param cua GET /api/majors + GET /api/schools,
va ca hai router dung chung `normalize()` o day. Thuat toan giu nguyen: cong y
het ban FE cu (`hocphi-info-fe/src/app/api/search/route.ts`, cung da xoa).
"""

import unicodedata

# So ky tu toi thieu (sau khi chuan hoa) de bat dau loc. Ngan hon -> tra [].
MIN_QUERY_LEN = 2


def normalize(text: str) -> str:
    """Bo dau tieng Viet + lowercase — vd "Bách khoa" -> "bach khoa"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return without_marks.replace("đ", "d").strip()
