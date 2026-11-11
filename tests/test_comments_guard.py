"""Luat thuan cua binh luan an danh (app/comments_guard.py) — khong can DB/HTTP."""

import pytest
from app import comments_guard as guard


@pytest.mark.parametrize(
    ("key", "school", "major"),
    [
        ("nganh", None, None),
        ("truong", None, None),
        ("bai-viet", None, None),
        ("truong/ueh", "ueh", None),
        (
            "nganh/dh-bach-khoa-tphcm/khoa-hoc-may-tinh",
            "dh-bach-khoa-tphcm",
            "khoa-hoc-may-tinh",
        ),
        ("bai-viet/hoc-phi-cntt-2026", None, None),
    ],
)
def test_parse_thread_key_valid(
    key: str, school: str | None, major: str | None
) -> None:
    ref = guard.parse_thread_key(key)
    assert ref is not None
    assert (ref.key, ref.school_slug, ref.major_slug) == (key, school, major)


@pytest.mark.parametrize(
    "key",
    [
        "",
        "so-sanh",
        "truong/",
        "truong/UEH",
        "truong/a/b",
        "nganh/ueh",
        "truong/../x",
        "bai-viet/a b",
        "truong/ueh-",
        "/truong/ueh",
        "x" * 300,
    ],
)
def test_parse_thread_key_invalid(key: str) -> None:
    assert guard.parse_thread_key(key) is None


def test_normalize_body() -> None:
    raw = "  Xin chào\r\n\r\n\r\n\r\nbạn\t ơi ​ \x07 \n"
    assert guard.normalize_body(raw) == "Xin chào\n\nbạn  ơi"
    # NFD (macOS) -> NFC: do dai tinh dung theo ky tu nguoi doc thay.
    assert guard.normalize_body("Học phí") == "Học phí"


def test_normalize_name() -> None:
    assert guard.normalize_name(None) is None
    assert guard.normalize_name("   ") is None
    assert guard.normalize_name("  Minh   Anh ") == "Minh Anh"


@pytest.mark.parametrize(
    "body",
    [
        "Học phí 35.200.000 đồng/năm",
        "Năm học 2026-2027 tăng 8-10%/năm",
        "Trường ở TP.HCM, cơ sở Q.10",
        "Bảo hiểm 0,68 triệu",
        "Học phí khoảng 0.5 triệu/tín chỉ",
    ],
)
def test_content_ok(body: str) -> None:
    assert guard.content_error(body, None) is None


@pytest.mark.parametrize(
    ("body", "name", "code"),
    [
        ("ab", None, "too_short"),
        ("x" * 2001, None, "too_long"),
        ("Nội dung ổn", "n" * 41, "name_too_long"),
        ("Xem tại abc.xyz/hocphi nhé", None, "contains_link"),
        ("Vào www.example để xem", None, "contains_link"),
        ("Link https://example", None, "contains_link"),
        ("Gọi mình 0912 345 678", None, "contains_phone"),
        ("Zalo +84 912345678", None, "contains_phone"),
        ("Liên hệ 0912.345.678", None, "contains_phone"),
        ("Nội dung ổn", "spam.vn", "contains_link"),
    ],
)
def test_content_errors(body: str, name: str | None, code: str) -> None:
    assert guard.content_error(body, name) == code


def test_author_tag_per_thread() -> None:
    a1 = guard.author_tag("truong/ueh", "1.2.3.4")
    assert a1 == guard.author_tag("truong/ueh", "1.2.3.4")
    assert len(a1) == 4
    assert a1 != guard.author_tag("truong/ueh", "5.6.7.8")
    assert guard.ip_hash("1.2.3.4") != "1.2.3.4"


async def test_verify_turnstile_skips_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard.settings, "turnstile_secret_key", None)
    assert await guard.verify_turnstile(None, "1.1.1.1") is True


async def test_verify_turnstile_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guard.settings, "turnstile_secret_key", "secret")
    assert await guard.verify_turnstile(None, "1.1.1.1") is False
