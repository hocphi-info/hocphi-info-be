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


# Do dai toi thieu cua tu khoa de khop TIEN TO alias (ngan hon chi khop khi BANG han).
MIN_ALIAS_PREFIX_LEN = 3


def alias_matches(query: str, alias: str) -> bool:
    """`query`/`alias` da qua normalize(). Khop khi BANG nhau, hoac `alias` bat dau
    bang `query` (query >= 3 ky tu) — KHONG khop chuoi con: "it" nam trong "digital"
    nhung khong duoc ra "Digital Art" chi vi alias "it" cua Cong nghe thong tin.
    FE (`hocphi-info-fe/src/lib/text.ts`) phai giu CUNG quy tac nay."""
    if query == alias:
        return True
    return len(query) >= MIN_ALIAS_PREFIX_LEN and alias.startswith(query)
