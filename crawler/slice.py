"""Buoc 3 — cat lat: giu lai doan co hoc phi, vut phan con lai.

    uv run python -m crawler.slice <slug> [--window 400]

Muc dich la GIAM VIEC CHO AI, khong phai thay AI. Mot de an tuyen sinh 60 trang
~40k token; sau khi cat con ~3k. Doc 3k token re hon doc 40k token khoang 13 lan,
va do la khoan tiet kiem duy nhat khong danh doi gi ca (xem docs/ai-crawler.md §3).

HTML: bo script/style, go tag, cat quanh moi lan xuat hien tu khoa.
PDF : KHONG parse o day — de Claude Code doc truc tiep bang `Read(pages=...)`,
      vi PDF ban scan thi khong co text de cat, va Claude doc anh duoc.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

WORK_DIR = Path(__file__).parent / "work"

# Tu khoa dinh vi. Bo dau truoc khi so khop nen "học phí" va "hoc phi" deu trung.
#
# "trieu dong" (KHONG bat buoc "/nam" theo sau) la muc quan trong: bang gia
# thuong ghi "55 trieu dong" roi de nam hoc ngam hieu tu tieu de bang ("Hoc phi
# nam 2026-2027"), khong lap lai "/nam" o tung dong. Phat hien that o NEU
# (2026-09-05): bang hoc phi ~30 chuong trinh tieng Anh dung dung dinh dang nay
# — thieu "trieu dong" trong danh sach nay khien ca bang (5+ muc gia, hang chuc
# chuong trinh) roi ra ngoai cua so tu khoa va bi CAT MAT, vi 2 lan xuat hien
# "hoc phi" gan nhat (dau va cuoi doan) cach nhau qua 2x window nen khong gop
# lien duoc. Neu ban thay `[TRONG]` hoac nghi ngo bang bi cat giua chung, doc
# lai TOAN BO raw HTML/PDF truc tiep — dung chi tin slice.
TU_KHOA = (
    "hoc phi",
    "muc thu",
    "dong/nam",
    "dong/thang",
    "dong/tin chi",
    "trieu dong",
    "/nam hoc",
    "tin chi",
    "hoc ky",
)

_THE_BO = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_THE = re.compile(r"<[^>]+>")
_KHOANG_TRANG = re.compile(r"[ \t\xa0]+")
_DONG_TRONG = re.compile(r"\n{3,}")


def bo_dau(s: str) -> str:
    """Bo dau tieng Viet de so khop tu khoa khong phu thuoc dau."""
    tach = unicodedata.normalize("NFD", s)
    khong_dau = "".join(c for c in tach if unicodedata.category(c) != "Mn")
    return khong_dau.replace("đ", "d").replace("Đ", "D").lower()


def html_sang_text(raw: str) -> str:
    s = _THE_BO.sub(" ", raw)
    s = _THE.sub("\n", s)
    s = html.unescape(s)
    s = _KHOANG_TRANG.sub(" ", s)
    s = "\n".join(d.strip() for d in s.split("\n") if d.strip())
    return _DONG_TRONG.sub("\n\n", s)


@dataclass(frozen=True)
class Lat:
    """1 doan van ban duoc giu lai, kem vi tri de truy nguoc."""

    offset: int
    text: str


def cat_lat(text: str, window: int = 400) -> list[Lat]:
    """Giu cac doan quanh moi lan xuat hien tu khoa; gop doan chong lan."""
    phang = bo_dau(text)
    vi_tri: list[int] = []
    for tu in TU_KHOA:
        vi_tri.extend(m.start() for m in re.finditer(re.escape(tu), phang))
    if not vi_tri:
        return []

    khoang = sorted((max(0, v - window), min(len(text), v + window)) for v in vi_tri)
    gop: list[list[int]] = []
    for dau, cuoi in khoang:
        if gop and dau <= gop[-1][1]:
            gop[-1][1] = max(gop[-1][1], cuoi)
        else:
            gop.append([dau, cuoi])
    return [Lat(offset=d, text=text[d:c]) for d, c in gop]


def uoc_token(s: str) -> int:
    """Uoc luong tho: tieng Viet ~3 ky tu/token. Du de bao cao muc giam."""
    return len(s) // 3


def xu_ly_truong(slug: str, window: int) -> int:
    meta_path = WORK_DIR / slug / "meta.json"
    if not meta_path.exists():
        print(f"Chua co {meta_path} — chay crawler.fetch truoc.", file=sys.stderr)
        return 1

    meta = json.loads(meta_path.read_text())
    out_dir = WORK_DIR / slug / "slices"
    out_dir.mkdir(parents=True, exist_ok=True)

    for f in meta["files"]:
        duong_dan = WORK_DIR / f["path"]
        ten = Path(f["path"]).stem

        if duong_dan.suffix == ".pdf":
            print(f"[bo qua] {f['url']}")
            print("         PDF — Claude Code doc truc tiep bang Read(pages=...)")
            continue

        raw = duong_dan.read_text(encoding="utf-8", errors="replace")
        text = html_sang_text(raw)
        lats = cat_lat(text, window)

        if not lats:
            print(f"[TRONG] {f['url']}")
            print(f"        {uoc_token(text):,} token, khong thay tu khoa hoc phi")
            print("        => tai lieu nay khong co bang hoc phi, tim nguon khac")
            continue

        noi_dung = "\n\n---\n\n".join(f"[offset {ln.offset}]\n{ln.text}" for ln in lats)
        dich = out_dir / f"{ten}.txt"
        dich.write_text(noi_dung, encoding="utf-8")

        truoc, sau = uoc_token(text), uoc_token(noi_dung)
        ti_le = f"{truoc / sau:.1f}x" if sau else "n/a"
        print(f"[ok] {f['url']}")
        print(f"     {truoc:,} -> {sau:,} token (giam {ti_le}), {len(lats)} lat")
        print(f"     -> {dich.relative_to(WORK_DIR.parent)}")

    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--window", type=int, default=400, help="so ky tu moi ben tu khoa")
    args = ap.parse_args()
    raise SystemExit(xu_ly_truong(args.slug, args.window))


if __name__ == "__main__":
    main()
