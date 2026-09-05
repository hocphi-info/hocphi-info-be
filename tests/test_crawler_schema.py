"""Test cho crawler/schema.py — cac rang buoc chan du lieu sai.

Cac case o day KHONG phai gia dinh: chung lay tu lan chay that dau tien tren UIT
(2026-09-04), noi model doc nham cot va bia so hoc phi/nam tu don gia tin chi.
Xem `.claude/skills/crawl-truong/SKILL.md` muc "Bay da gap that".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from app import enums
from crawler.schema import (
    DEFAULT_CREDITS_PER_YEAR,
    TuitionRow,
    quy_doi_ve_dong_nam,
)
from pydantic import ValidationError

FETCHED = "2025-09-04T16:38:00+00:00"


def _row(**ghi_de: Any) -> dict[str, Any]:
    """Dong hop le (UIT chuong trinh chuan 2025-2026), ghi de tung truong de test."""
    goc: dict[str, Any] = {
        "school_slug": "uit",
        "major_slug": None,
        "major_name_raw": "Cong nghe Thong tin — Chuong trinh chuan",
        "track": "dai_tra",
        "language": "vi",
        "campus": None,
        "academic_year": "2025-2026",
        "amount_original": 37_000_000,
        "unit_original": "dong_nam",
        "credits_per_year_assumed": None,
        "amount_per_year": 37_000_000,
        "is_projected": False,
        "confidence": "published_unverified",
        "source_url": "https://khtc.uit.edu.vn/x.pdf",
        "source_doc_type": "thong_bao_hoc_phi",
        "source_published_date": "2025-08-18",
        "fetched_at": FETCHED,
        "evidence": {
            "quote": "Hoc phi hoc moi: 37.000.000 dong/Nam hoc",
            "page": 2,
        },
    }
    return goc | ghi_de


def test_dong_hop_le_di_qua() -> None:
    r = TuitionRow.model_validate(_row())
    assert r.amount_per_year == 37_000_000
    assert r.needs_review is True  # major_slug=None => cho nguoi duyet
    assert r.review_reason is not None


@pytest.mark.parametrize(
    ("amount", "unit", "credits", "mong_doi"),
    [
        (37_000_000, enums.TuitionUnit.DONG_NAM, None, 37_000_000),
        (3_000_000, enums.TuitionUnit.DONG_THANG, None, 30_000_000),
        (1_300_000, enums.TuitionUnit.DONG_TIN_CHI, 32, 41_600_000),
    ],
)
def test_quy_doi(
    amount: int, unit: enums.TuitionUnit, credits: int | None, mong_doi: int
) -> None:
    assert quy_doi_ve_dong_nam(amount, unit, credits) == mong_doi


def test_quy_doi_toan_khoa() -> None:
    # HUTECH khoa 2026, CNTT: 247.500.000 dong / 4 nam = 61.875.000 dong/nam.
    assert (
        quy_doi_ve_dong_nam(
            247_500_000, enums.TuitionUnit.DONG_TOAN_KHOA, None, Decimal("4")
        )
        == 61_875_000
    )


def test_quy_doi_toan_khoa_nam_le() -> None:
    # HUTECH Dieu duong: 238.000.000 dong / 3.5 nam = 68.000.000 dong/nam.
    assert (
        quy_doi_ve_dong_nam(
            238_000_000, enums.TuitionUnit.DONG_TOAN_KHOA, None, Decimal("3.5")
        )
        == 68_000_000
    )


def test_model_tu_tinh_sai_thi_bi_chan() -> None:
    """Rang buoc quan trong nhat: amount_per_year phai = ket qua quy doi."""
    with pytest.raises(ValidationError, match="khong khop quy doi"):
        # 3tr/thang => 30tr/nam, nhung khai 36tr (nhan 12 thay vi 10).
        TuitionRow.model_validate(
            _row(
                amount_original=3_000_000,
                unit_original="dong_thang",
                amount_per_year=36_000_000,
            )
        )


def test_tin_chi_thieu_so_tin_chi_thi_bi_chan() -> None:
    with pytest.raises(ValidationError, match="bat buoc co credits_per_year_assumed"):
        TuitionRow.model_validate(
            _row(
                amount_original=1_300_000,
                unit_original="dong_tin_chi",
                credits_per_year_assumed=None,
                amount_per_year=39_000_000,
            )
        )


def test_so_tin_chi_mac_dinh_bi_danh_dau_can_review() -> None:
    """Case UIT CLC: 1.15tr/TC x 30 mac dinh = 34,5tr — con so bia.

    Schema danh dau needs_review; `crawler.validate` bien no thanh LOI cung.
    """
    r = TuitionRow.model_validate(
        _row(
            track="chat_luong_cao",
            amount_original=1_150_000,
            unit_original="dong_tin_chi",
            credits_per_year_assumed=DEFAULT_CREDITS_PER_YEAR,
            amount_per_year=1_150_000 * DEFAULT_CREDITS_PER_YEAR,
        )
    )
    assert r.needs_review is True
    assert r.review_reason is not None
    assert "mac dinh" in r.review_reason


def test_toan_khoa_thieu_so_nam_thi_bi_chan() -> None:
    with pytest.raises(ValidationError, match="bat buoc co duration_years_assumed"):
        TuitionRow.model_validate(
            _row(
                amount_original=247_500_000,
                unit_original="dong_toan_khoa",
                duration_years_assumed=None,
                amount_per_year=61_875_000,
            )
        )


def test_toan_khoa_luon_bi_danh_dau_can_review() -> None:
    """HUTECH khoa 2026: hoc phi tron goi ca khoa, khong co muc tung nam rieng —
    chia deu la suy ra, luon can nguoi duyet (khac voi vi du hop le o dau file,
    o day danh dau vi don vi toan_khoa, khong phai vi thieu major_slug)."""
    r = TuitionRow.model_validate(
        _row(
            major_slug="cong-nghe-thong-tin",
            amount_original=247_500_000,
            unit_original="dong_toan_khoa",
            duration_years_assumed=4,
            amount_per_year=61_875_000,
            confidence="published_unverified",
        )
    )
    assert r.needs_review is True
    assert r.review_reason is not None
    assert "toan khoa" in r.review_reason


@pytest.mark.parametrize("nam", ["2025", "2025-2027", "25-26", "2026-2025"])
def test_academic_year_sai_dinh_dang(nam: str) -> None:
    with pytest.raises(ValidationError):
        TuitionRow.model_validate(_row(academic_year=nam))


def test_thieu_trich_dan_thi_bi_chan() -> None:
    """Khong co bang chung => khong co record (nguyen tac 2 cua skill)."""
    with pytest.raises(ValidationError):
        TuitionRow.model_validate(_row(evidence={"quote": "ngan", "page": 2}))


def test_ngoai_bien_do_bi_danh_dau() -> None:
    r = TuitionRow.model_validate(
        _row(amount_original=42_000, amount_per_year=42_000)  # quen 3 so 0
    )
    assert r.needs_review is True
    assert r.review_reason is not None
    assert "ngoai bien do" in r.review_reason


def test_truong_la_bi_chan() -> None:
    """extra=forbid — model bia them truong thi hong ngay, khong am tham."""
    with pytest.raises(ValidationError):
        TuitionRow.model_validate(_row(hoc_phi_ky_he=1_725_000))
