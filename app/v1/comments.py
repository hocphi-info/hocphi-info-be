"""Binh luan an danh, long nhau — duong GHI cong khai duy nhat cua API.

    GET    /api/v1/comments?thread=&sort=&offset=   20 goc / trang + toan bo con chau
    POST   /api/v1/comments                         tao binh luan / tra loi
    DELETE /api/v1/comments/{id}                    tu xoa trong 15 phut (header)
    POST   /api/v1/comments/{id}/reports            bao cao; >= 3 IP khac nhau -> tu an

Khong tai khoan, khong API quan tri: owner kiem duyet bang
`scripts/moderate_comments.py`. Chong spam nhieu lop: chan link/SDT, gioi han toc
do theo IP, Cloudflare Turnstile, tu an khi bi bao cao. Xem
hocphi-info-fe/docs/plans/2026-11-11-002-feat-binh-luan-an-danh-nested-plan.md.

Loi tra ve co cau truc `{"detail": {"code": "...", "message": "..."}}` — FE dich
`code` sang cau tieng Viet cua minh, `message` la du phong.
"""

from __future__ import annotations

import hmac
import math
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import comments_guard as guard
from app.db import get_session
from app.enums import CommentReportReason, CommentSort
from app.models import Comment, CommentReport, Major, Program, School
from app.schemas.common import CamelModel

router = APIRouter(tags=["comments"])
logger = structlog.get_logger("hocphi.comments")

PAGE_SIZE = 20
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = timedelta(minutes=10)
DELETE_WINDOW = timedelta(minutes=15)
AUTO_HIDE_REPORTS = 3


# ── Pydantic in/out ──────────────────────────────────────────────────────────
class CommentOut(CamelModel):
    """1 nut cua cay. Bi an/xoa nhung con tra loi hien thi -> `isHidden=true`, cac
    truong noi dung = null (giu cho de chuoi khong dut)."""

    id: str
    parent_id: str | None
    root_id: str | None
    depth: int
    # null = "An danh" (FE tu hien chu).
    author_name: str | None
    author_tag: str | None
    body: str | None
    is_hidden: bool
    created_at: datetime


class CommentListOut(CamelModel):
    thread_key: str
    sort: CommentSort
    # So binh luan dang hien thi cua CA chuoi (moi cap), cho tieu de khoi.
    total: int
    # Danh sach PHANG: cac goc cua trang nay (theo `sort`) roi toan bo con chau
    # (cu -> moi). FE tu dung cay theo `parentId`.
    comments: list[CommentOut]
    next_offset: int | None


class CommentCreateIn(CamelModel):
    # max_length o day chi chan payload qua lon; luat that (3-2000 ky tu, ten <= 40)
    # kiem sau khi chuan hoa de tra ma loi rieng.
    thread_key: str = Field(max_length=220)
    parent_id: str | None = Field(default=None, max_length=40)
    author_name: str | None = Field(default=None, max_length=500)
    body: str = Field(max_length=10_000)
    turnstile_token: str | None = Field(default=None, max_length=4096)


class CommentCreatedOut(CamelModel):
    comment: CommentOut
    # Ma bi mat de tu xoa trong 15 phut — chi tra 1 lan, DB chi luu ban bam.
    delete_token: str


class CommentReportIn(CamelModel):
    reason: CommentReportReason


class CommentReportOut(CamelModel):
    hidden: bool


# ── Helper ────────────────────────────────────────────────────────────────────
_MESSAGES = {
    "invalid_thread": "Khóa chuỗi bình luận không hợp lệ.",
    "thread_not_found": "Trang này không còn tồn tại.",
    "parent_not_found": "Bình luận bạn trả lời không còn tồn tại.",
    "too_short": "Bình luận cần ít nhất 3 ký tự.",
    "too_long": "Bình luận tối đa 2000 ký tự.",
    "name_too_long": "Tên hiển thị tối đa 40 ký tự.",
    "contains_link": "Bình luận không được chứa đường link.",
    "contains_phone": "Bình luận không được chứa số điện thoại.",
    "rate_limited": "Bạn gửi hơi nhanh, thử lại sau ít phút.",
    "turnstile_failed": "Chưa xác minh được bạn là người.",
    "not_found": "Không tìm thấy bình luận.",
    "invalid_token": "Bạn không có quyền xóa bình luận này.",
    "delete_window_expired": "Đã quá 15 phút, không thể tự xóa nữa.",
}


def _error(
    status: int, code: str, headers: dict[str, str] | None = None, **extra: object
) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": _MESSAGES[code], **extra},
        headers=headers,
    )


def _is_visible(c: Comment) -> bool:
    return c.deleted_at is None and c.hidden_at is None


def _visible_clause(model: type[Comment]) -> ColumnElement[bool]:
    return and_(model.deleted_at.is_(None), model.hidden_at.is_(None))


def _to_out(c: Comment) -> CommentOut:
    visible = _is_visible(c)
    return CommentOut(
        id=c.id,
        parent_id=c.parent_id,
        root_id=c.root_id,
        depth=c.depth,
        author_name=c.author_name if visible else None,
        author_tag=c.author_tag if visible else None,
        body=c.body if visible else None,
        is_hidden=not visible,
        created_at=c.created_at,
    )


def _prune(nodes: list[Comment]) -> list[Comment]:
    """Giu nut hien thi duoc + nut an/xoa CON hau due hien thi duoc (lam cho giu
    chuoi). Duyet tu sau len nong (khong de quy -> cay sau bao nhieu cung duoc)."""
    keep: set[str] = set()
    for c in sorted(nodes, key=lambda n: n.depth, reverse=True):
        if _is_visible(c) or c.id in keep:
            keep.add(c.id)
            if c.parent_id is not None:
                keep.add(c.parent_id)
    return [c for c in nodes if c.id in keep]


def _parse_thread(thread_key: str) -> guard.ThreadRef:
    ref = guard.parse_thread_key(thread_key)
    if ref is None:
        raise _error(422, "invalid_thread")
    return ref


# ── GET ───────────────────────────────────────────────────────────────────────
@router.get("/api/v1/comments", response_model=CommentListOut)
async def list_comments(
    thread: str = Query(..., max_length=220, description="vd truong/ueh"),
    sort: CommentSort = CommentSort.NEWEST,
    offset: int = Query(0, ge=0, le=100_000),
    session: AsyncSession = Depends(get_session),
) -> CommentListOut:
    ref = _parse_thread(thread)

    desc = aliased(Comment)
    has_visible_desc = exists().where(desc.root_id == Comment.id, _visible_clause(desc))
    order = (
        (Comment.created_at.desc(), Comment.id.desc())
        if sort == CommentSort.NEWEST
        else (Comment.created_at.asc(), Comment.id.asc())
    )
    roots = list(
        (
            await session.scalars(
                select(Comment)
                .where(
                    Comment.thread_key == ref.key,
                    Comment.parent_id.is_(None),
                    or_(_visible_clause(Comment), has_visible_desc),
                )
                .order_by(*order)
                .offset(offset)
                .limit(PAGE_SIZE + 1)
            )
        ).all()
    )
    has_more = len(roots) > PAGE_SIZE
    roots = roots[:PAGE_SIZE]

    descendants: list[Comment] = []
    if roots:
        descendants = list(
            (
                await session.scalars(
                    select(Comment)
                    .where(Comment.root_id.in_([r.id for r in roots]))
                    .order_by(Comment.created_at.asc(), Comment.id.asc())
                )
            ).all()
        )

    total = await session.scalar(
        select(func.count())
        .select_from(Comment)
        .where(Comment.thread_key == ref.key, _visible_clause(Comment))
    )

    return CommentListOut(
        thread_key=ref.key,
        sort=sort,
        total=total or 0,
        comments=[_to_out(c) for c in _prune(roots + descendants)],
        next_offset=offset + PAGE_SIZE if has_more else None,
    )


# ── POST ──────────────────────────────────────────────────────────────────────
async def _check_thread_exists(session: AsyncSession, ref: guard.ThreadRef) -> None:
    if ref.school_slug is None:
        return  # trang danh sach / bai viet: bai viet nam o FE, chi kiem dinh dang
    if ref.major_slug is None:
        found = await session.scalar(
            select(School.id).where(
                School.slug == ref.school_slug, School.deleted_at.is_(None)
            )
        )
    else:
        found = await session.scalar(
            select(Program.id)
            .join(School, Program.school_id == School.id)
            .join(Major, Program.major_id == Major.id)
            .where(
                School.slug == ref.school_slug,
                Major.slug == ref.major_slug,
                School.deleted_at.is_(None),
                Major.deleted_at.is_(None),
                Program.deleted_at.is_(None),
            )
            .limit(1)
        )
    if found is None:
        raise _error(404, "thread_not_found")


async def _check_rate_limit(session: AsyncSession, ip_h: str) -> None:
    now = datetime.now(UTC)
    count, oldest = (
        await session.execute(
            select(func.count(), func.min(Comment.created_at)).where(
                Comment.ip_hash == ip_h,
                Comment.created_at > now - RATE_LIMIT_WINDOW,
            )
        )
    ).one()
    if count >= RATE_LIMIT_COUNT:
        retry = max(1, math.ceil((oldest + RATE_LIMIT_WINDOW - now).total_seconds()))
        raise _error(
            429,
            "rate_limited",
            headers={"Retry-After": str(retry)},
            retryAfterSeconds=retry,
        )


@router.post("/api/v1/comments", response_model=CommentCreatedOut, status_code=201)
async def create_comment(
    payload: CommentCreateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CommentCreatedOut:
    # 1-2. Chuan hoa + luat noi dung (re nhat, chay truoc).
    body = guard.normalize_body(payload.body)
    name = guard.normalize_name(payload.author_name)
    if code := guard.content_error(body, name):
        raise _error(422, code)

    # 3. Chuoi + binh luan cha.
    ref = _parse_thread(payload.thread_key)
    await _check_thread_exists(session, ref)
    parent: Comment | None = None
    if payload.parent_id is not None:
        parent = await session.get(Comment, payload.parent_id)
        if parent is None or parent.thread_key != ref.key or not _is_visible(parent):
            raise _error(404, "parent_not_found")

    # 4. Gioi han toc do theo IP.
    ip = guard.client_ip(request)
    ip_h = guard.ip_hash(ip)
    await _check_rate_limit(session, ip_h)

    # 5. Chong bot (goi ra ngoai — de sau cung, sau cac buoc re).
    if not await guard.verify_turnstile(payload.turnstile_token, ip):
        raise _error(400, "turnstile_failed")

    # 6. Ghi.
    token = secrets.token_urlsafe(24)
    comment = Comment(
        thread_key=ref.key,
        parent_id=parent.id if parent else None,
        root_id=(parent.root_id or parent.id) if parent else None,
        depth=parent.depth + 1 if parent else 0,
        author_name=name,
        author_tag=guard.author_tag(ref.key, ip),
        body=body,
        ip_hash=ip_h,
        delete_token_hash=guard.hash_delete_token(token),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)  # lay id / created_at do DB sinh
    logger.info(
        "comment_created", comment_id=comment.id, thread=ref.key, depth=comment.depth
    )
    return CommentCreatedOut(comment=_to_out(comment), delete_token=token)


# ── DELETE ────────────────────────────────────────────────────────────────────
@router.delete("/api/v1/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    x_delete_token: str = Header(..., max_length=200),
    session: AsyncSession = Depends(get_session),
) -> Response:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise _error(404, "not_found")
    if not hmac.compare_digest(
        guard.hash_delete_token(x_delete_token), comment.delete_token_hash
    ):
        raise _error(403, "invalid_token")
    now = datetime.now(UTC)
    if now - comment.created_at > DELETE_WINDOW:
        raise _error(409, "delete_window_expired")
    comment.deleted_at = now
    comment.updated_at = now
    await session.commit()
    logger.info("comment_self_deleted", comment_id=comment.id)
    return Response(status_code=204)


# ── REPORT ────────────────────────────────────────────────────────────────────
@router.post("/api/v1/comments/{comment_id}/reports", response_model=CommentReportOut)
async def report_comment(
    comment_id: str,
    payload: CommentReportIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CommentReportOut:
    comment = await session.get(Comment, comment_id)
    if comment is None or not _is_visible(comment):
        raise _error(404, "not_found")

    # Moi IP bao cao 1 binh luan 1 lan; bao lai = khong lam gi (idempotent).
    await session.execute(
        pg_insert(CommentReport)
        .values(
            comment_id=comment.id,
            ip_hash=guard.ip_hash(guard.client_ip(request)),
            reason=payload.reason,
        )
        .on_conflict_do_nothing(index_elements=["comment_id", "ip_hash"])
    )
    n_reports = await session.scalar(
        select(func.count())
        .select_from(CommentReport)
        .where(CommentReport.comment_id == comment.id)
    )
    hidden = (n_reports or 0) >= AUTO_HIDE_REPORTS
    if hidden:
        now = datetime.now(UTC)
        comment.hidden_at = now
        comment.hidden_reason = "auto_reports"
        comment.updated_at = now
        logger.info("comment_auto_hidden", comment_id=comment.id, reports=n_reports)
    await session.commit()
    return CommentReportOut(hidden=hidden)
