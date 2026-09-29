"""Xuat hop dong API ra `openapi.json` (commit vao repo).

    uv run python -m scripts.export_openapi          # ghi openapi.json
    uv run python -m scripts.export_openapi --check  # exit 1 neu file da cu

FE (`hocphi-info-fe`) sinh type TypeScript tu file nay (`npm run gen:api`),
`tests/test_openapi_contract.py` va CI dung `--check` de bat truong hop sua
response model ma quen xuat lai. Khong can DB: `app.openapi()` chi doc schema
Pydantic/route, engine async chi ket noi khi co request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.main import app

OPENAPI_PATH = Path(__file__).parent.parent / "openapi.json"


def render() -> str:
    """Chuoi JSON on dinh (indent 2, giu tieng Viet, xuong dong cuoi) de diff sach."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="chi kiem tra, khong ghi file"
    )
    args = parser.parse_args()

    expected = render()
    if args.check:
        current = OPENAPI_PATH.read_text() if OPENAPI_PATH.exists() else ""
        if current != expected:
            print(
                "openapi.json da cu — chay `make openapi` roi commit.", file=sys.stderr
            )
            return 1
        print("openapi.json khop voi app.openapi().")
        return 0

    OPENAPI_PATH.write_text(expected)
    print(f"Da ghi {OPENAPI_PATH.name} ({len(expected)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
