"""Kiem duyet binh luan an danh — thay cho trang/API quan tri (co y khong co).

    uv run python -m scripts.moderate_comments reported           # nhieu bao cao nhat
    uv run python -m scripts.moderate_comments recent [--thread K] [--limit N]
    uv run python -m scripts.moderate_comments hide ID [--reason R]  # an (giu cho)
    uv run python -m scripts.moderate_comments unhide ID             # hien lai
    uv run python -m scripts.moderate_comments delete ID             # xoa mem

Tren production:
    fly ssh console -C "python -m scripts.moderate_comments reported"

Binh luan an/xoa ma con tra loi ben duoi van hien "[da an]" de chuoi khong dut
(API tu lo viec do) — script chi doi `hidden_at` / `deleted_at`.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from app.db import SessionLocal
from app.models import Comment, CommentReport
from sqlalchemy import func, select


def _status(c: Comment) -> str:
    if c.deleted_at is not None:
        return "DA XOA"
    if c.hidden_at is not None:
        return f"AN ({c.hidden_reason or '-'})"
    return "hien"


def _line(c: Comment, n_reports: int | None = None) -> str:
    who = f"{c.author_name or 'An danh'} #{c.author_tag}"
    body = c.body.replace("\n", " ")
    if len(body) > 100:
        body = body[:97] + "..."
    reports = f" · {n_reports} bao cao" if n_reports is not None else ""
    return (
        f"{c.id}  [{_status(c)}]{reports}\n"
        f"    {c.created_at:%Y-%m-%d %H:%M} · {c.thread_key} · cap {c.depth} · {who}\n"
        f"    {body}"
    )


async def cmd_reported(limit: int) -> None:
    async with SessionLocal() as s:
        n = func.count(CommentReport.id).label("n")
        rows = (
            await s.execute(
                select(Comment, n)
                .join(CommentReport, CommentReport.comment_id == Comment.id)
                .group_by(Comment.id)
                .order_by(n.desc(), Comment.created_at.desc())
                .limit(limit)
            )
        ).all()
    if not rows:
        print("Chua co bao cao nao.")
    for c, count in rows:
        print(_line(c, count))


async def cmd_recent(thread: str | None, limit: int) -> None:
    async with SessionLocal() as s:
        q = select(Comment).order_by(Comment.created_at.desc()).limit(limit)
        if thread:
            q = q.where(Comment.thread_key == thread)
        rows = (await s.scalars(q)).all()
    if not rows:
        print("Chua co binh luan nao.")
    for c in rows:
        print(_line(c))


async def _update(comment_id: str, action: str, reason: str | None) -> None:
    async with SessionLocal() as s:
        c = await s.get(Comment, comment_id)
        if c is None:
            raise SystemExit(f"Khong tim thay binh luan {comment_id}")
        now = datetime.now(UTC)
        if action == "hide":
            c.hidden_at, c.hidden_reason = now, reason or "owner"
        elif action == "unhide":
            c.hidden_at, c.hidden_reason = None, None
        elif action == "delete":
            c.deleted_at = now
        c.updated_at = now
        await s.commit()
        print(_line(c))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("reported", help="binh luan bi bao cao, nhieu nhat truoc")
    p.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("recent", help="binh luan moi nhat")
    p.add_argument("--thread", help="vd truong/ueh")
    p.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("hide", help="an 1 binh luan")
    p.add_argument("id")
    p.add_argument("--reason", help="ghi chu ly do (mac dinh: owner)")
    for name in ("unhide", "delete"):
        sub.add_parser(name, help=f"{name} 1 binh luan").add_argument("id")
    args = parser.parse_args()

    if args.cmd == "reported":
        asyncio.run(cmd_reported(args.limit))
    elif args.cmd == "recent":
        asyncio.run(cmd_recent(args.thread, args.limit))
    else:
        asyncio.run(_update(args.id, args.cmd, getattr(args, "reason", None)))


if __name__ == "__main__":
    main()
