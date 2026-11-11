"""Cac "cua gac" cho binh luan an danh — ham thuan (tru `verify_turnstile` goi mang).

Tach khoi router (`app/v1/comments.py`) de test rieng tung luat ma khong can HTTP:
chuan hoa noi dung, chan link / so dien thoai, doc khoa chuoi, bam IP.

Vi sao bam HMAC (co khoa) ma khong sha256 tron: khong gian IPv4 chi ~4 ty gia tri,
sha256 tron thi ai co DB la do nguoc ra IP trong vai phut. HMAC can them
`COMMENT_SECRET` (chi nam o Fly secrets) moi do duoc.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass

import httpx
import structlog
from fastapi import Request

from app.config import settings

logger = structlog.get_logger("hocphi.comments")

BODY_MIN = 3
BODY_MAX = 2000
NAME_MAX = 40
TAG_LEN = 4

# ── Khoa chuoi (thread key) ────────────────────────────────────────────────────
_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_THREAD_RE = re.compile(
    rf"^(?:(?P<page>nganh|truong|bai-viet)"
    rf"|truong/(?P<school>{_SLUG})"
    rf"|nganh/(?P<p_school>{_SLUG})/(?P<p_major>{_SLUG})"
    rf"|bai-viet/(?P<post>{_SLUG}))$"
)


@dataclass(frozen=True)
class ThreadRef:
    """Khoa chuoi da doc: dung de kiem tra truong / nganh-truong co ton tai."""

    key: str
    school_slug: str | None = None
    major_slug: str | None = None


def parse_thread_key(key: str) -> ThreadRef | None:
    """`None` neu sai dinh dang. Slug dai toi da 100 ky tu moi phan."""
    if len(key) > 220:
        return None
    m = _THREAD_RE.match(key)
    if m is None:
        return None
    if m["school"]:
        return ThreadRef(key=key, school_slug=m["school"])
    if m["p_school"]:
        return ThreadRef(key=key, school_slug=m["p_school"], major_slug=m["p_major"])
    return ThreadRef(key=key)


# ── Chuan hoa + kiem noi dung ─────────────────────────────────────────────────
_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"\s+")

# Link: http(s)://, www., hoac ten mien tran co duoi pho bien (abc.xyz, web.vn...).
_LINK_RE = re.compile(
    r"https?://|www\.|"
    r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\."
    r"(?:com|vn|net|org|info|io|xyz|me|co|edu|gov|biz|online|site|top|link|ly|app|dev)"
    r"\b",
    re.IGNORECASE,
)
# SDT Viet Nam: 0xxxxxxxxx / +84xxxxxxxxx (9-11 chu so sau tien to), cho phep
# ngan cach bang dau cach, cham, gach. Khong khop so tien ("35.200.000" khong bat
# dau bang 0) hay nam hoc ("2026-2027").
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)")


def _strip_controls(s: str) -> str:
    # Giu \n; \t -> dau cach; bo moi ky tu dieu khien / dinh dang vo hinh khac.
    out = []
    for ch in s.replace("\t", " "):
        if ch == "\n" or unicodedata.category(ch)[0] != "C":
            out.append(ch)
    return "".join(out)


def normalize_body(raw: str) -> str:
    """NFC (go tren macOS hay ra dang NFD) + \\r\\n -> \\n + bo ky tu dieu khien +
    cat khoang trang moi dong + gop >2 dong trong."""
    s = unicodedata.normalize("NFC", raw).replace("\r\n", "\n").replace("\r", "\n")
    s = _strip_controls(s)
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    return _BLANK_LINES.sub("\n\n", s).strip()


def normalize_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = _SPACES.sub(" ", _strip_controls(unicodedata.normalize("NFC", raw))).strip()
    return s or None


def content_error(body: str, name: str | None) -> str | None:
    """Ma loi dau tien gap phai (`too_short`, `contains_link`...) hoac `None`."""
    if len(body) < BODY_MIN:
        return "too_short"
    if len(body) > BODY_MAX:
        return "too_long"
    if name is not None and len(name) > NAME_MAX:
        return "name_too_long"
    for text in (body, name or ""):
        if _LINK_RE.search(text):
            return "contains_link"
        if _PHONE_RE.search(text):
            return "contains_phone"
    return None


# ── Danh tinh an danh ─────────────────────────────────────────────────────────
def client_ip(request: Request) -> str:
    """IP that cua nguoi dung. Tren Fly, proxy ghi `Fly-Client-IP` (ghi de gia tri
    client tu gui); chay local thi lay IP cua ket noi."""
    ip = request.headers.get("fly-client-ip")
    if ip:
        return ip.strip()
    return request.client.host if request.client else "unknown"


def _hmac(message: str) -> str:
    return hmac.new(
        settings.comment_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def ip_hash(ip: str) -> str:
    return _hmac(f"ip|{ip}")


def author_tag(thread_key: str, ip: str) -> str:
    """4 ky tu hex: cung nguoi + cung chuoi -> cung tag; khac chuoi -> khac tag."""
    return _hmac(f"tag|{thread_key}|{ip}")[:TAG_LEN]


def hash_delete_token(token: str) -> str:
    # Token ngau nhien 192 bit -> sha256 tron la du (khong the do nguoc).
    return hashlib.sha256(token.encode()).hexdigest()


# ── Cloudflare Turnstile ──────────────────────────────────────────────────────
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str | None, ip: str) -> bool:
    """Hoi Cloudflare token co hop le khong. Chua cau hinh secret -> cho qua (dev).

    Loi mang / timeout -> tu choi (fail closed): de bot khong lach duoc bang cach
    lam nghen. Router goi qua `comments_guard.verify_turnstile` nen test thay duoc
    bang monkeypatch.
    """
    secret = settings.turnstile_secret_key
    if not secret:
        logger.warning("turnstile_disabled")
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                TURNSTILE_VERIFY_URL,
                data={"secret": secret, "response": token, "remoteip": ip},
            )
        ok = bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError):
        logger.warning("turnstile_verify_error", exc_info=True)
        return False
    if not ok:
        logger.info("turnstile_rejected")
    return ok
