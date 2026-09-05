"""Buoc 2 — tai tai lieu ve dia, giu snapshot de doi chieu ve sau.

    uv run python -m crawler.fetch <slug> <url> [--doc-type de_an_tuyen_sinh]

Ghi ra crawler/work/<slug>/raw/<hash>.<ext> + meta.json (url, fetched_at,
content_type, sha256). Khong parse gi ca — parse la viec cua slice.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORK_DIR = Path(__file__).parent / "work"

# Dung `curl` chu khong urllib: nhieu site truong DH VN co chuoi chung chi thieu
# intermediate, urllib cua Python (khong co certifi) bao CERTIFICATE_VERIFY_FAILED
# trong khi curl dung trust store cua macOS thi qua. Doi lai: khong them dependency.

# Ghi ro danh tinh — de webmaster truong biet ai dang tai va lien he duoc.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) hocphi.info-crawler/0.1 "
    "(+https://github.com/hocphi-info; muc dich: tong hop hoc phi cong khai)"
)
TIMEOUT_GIAY = 30
MAX_BYTES = 50 * 1024 * 1024


def tai_ve(slug: str, url: str, doc_type: str) -> Path:
    """Tai 1 URL ve crawler/work/<slug>/raw/. Tra ve duong dan file."""
    raw_dir = WORK_DIR / slug / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    body, content_type, http_code = _curl(url)

    if http_code != 200:
        print(f"  [that bai] HTTP {http_code} — {url}", file=sys.stderr)
        if http_code in (403, 429):
            print("    Trang chan crawler. Bo qua, tim nguon khac.", file=sys.stderr)
        raise SystemExit(1)
    if len(body) > MAX_BYTES:
        raise SystemExit(f"File > {MAX_BYTES} bytes, bo qua: {url}")

    ext = _doan_duoi(url, content_type)
    digest = hashlib.sha256(body).hexdigest()
    dich = raw_dir / f"{digest[:16]}{ext}"
    dich.write_bytes(body)

    meta_path = WORK_DIR / slug / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"files": []}
    meta["files"] = [f for f in meta["files"] if f["url"] != url]
    meta["files"].append(
        {
            "url": url,
            "path": str(dich.relative_to(WORK_DIR)),
            "doc_type": doc_type,
            "content_type": content_type,
            "bytes": len(body),
            "sha256": digest,
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    print(f"  [ok] {len(body):,} bytes -> {dich.relative_to(WORK_DIR.parent)}")
    print(f"       content-type: {content_type or '(khong ro)'}")
    return dich


def _curl(url: str) -> tuple[bytes, str, int]:
    """Tra ve (body, content_type, http_code). Loi mang => SystemExit."""
    try:
        proc = subprocess.run(
            [
                "curl", "--silent", "--show-error", "--location",
                "--max-time", str(TIMEOUT_GIAY),
                "--max-filesize", str(MAX_BYTES),
                "--user-agent", USER_AGENT,
                "--write-out", "\n%{http_code}\t%{content_type}",
                url,
            ],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as e:  # pragma: no cover — macOS luon co curl
        raise SystemExit("Khong tim thay `curl` trong PATH") from e

    if proc.returncode != 0:
        loi = proc.stderr.decode("utf-8", "replace").strip()
        print(f"  [that bai] curl exit {proc.returncode}: {loi}", file=sys.stderr)
        raise SystemExit(1)

    # Tach dong cuoi (do --write-out them vao) khoi noi dung.
    body, _, duoi = proc.stdout.rpartition(b"\n")
    ma, _, ctype = duoi.decode("utf-8", "replace").partition("\t")
    return body, ctype.strip(), int(ma or 0)


def _doan_duoi(url: str, content_type: str) -> str:
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        return ".pdf"
    if "html" in content_type.lower():
        return ".html"
    return mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", help="slug truong, khop schools.slug")
    ap.add_argument("url")
    ap.add_argument(
        "--doc-type",
        default="khac",
        choices=["de_an_tuyen_sinh", "thong_bao_hoc_phi", "quy_dinh_nghe", "khac"],
    )
    args = ap.parse_args()
    print(f"Tai {args.url}")
    tai_ve(args.slug, args.url, args.doc_type)


if __name__ == "__main__":
    main()
