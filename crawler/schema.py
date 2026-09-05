"""Schema cho file trung gian `seeds/*.jsonl` — output cua AI-crawler.

Moi DONG trong JSONL = 1 muc hoc phi (1 chuong trinh x 1 nam hoc), o dang
DENORMALIZED: mang du thong tin de `scripts/seed.py` dung/tim ra program +
source tuong ung. Xem docs/ai-crawler.md §4.

Ba rang buoc quan trong duoc ep o day, khong phai o prompt:

1. `amount_per_year` PHAI khop voi cong thuc quy doi tu `amount_original`.
   Model chi doc so goc + don vi goc; viec nhan chia la cua code.
2. Moi dong PHAI co `evidence.quote` — cau trich nguyen van tu tai lieu.
   Khong trich duoc => vut dong do, khong doan.
3. `amount_per_year` phai nam trong bien do hop ly. Ngoai bien => needs_review.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from app import enums
from pydantic import BaseModel, Field, model_validator

# Bien do hop ly cho hoc phi dai hoc VN (dong/nam). Duoi can duoi thuong la
# nham don vi (ghi "4.2" y la 4.2 trieu); tren can tren thuong la nham cong
# thuc (nhan nham so tin chi) hoac la chuong trinh lien ket dat that.
MIN_PER_YEAR = 1_000_000
MAX_PER_YEAR = 1_000_000_000

# So tin chi/nam mac dinh khi truong cong bo theo dong/tin chi ma khong noi ro.
# KHONG dung ngam: neu phai dung mac dinh thi dong do bi danh dau needs_review.
DEFAULT_CREDITS_PER_YEAR = 30

ACADEMIC_YEAR_RE = re.compile(r"^\d{4}-\d{4}$")


def quy_doi_ve_dong_nam(
    amount_original: int,
    unit_original: enums.TuitionUnit,
    credits_per_year: int | None,
    duration_years: Decimal | None = None,
) -> int:
    """Quy doi so goc ve dong/nam. Day la NGUON SU THAT cho amount_per_year.

    Model khong duoc tu tinh — no chi dien amount_original + unit_original,
    con so cuoi cung do ham nay sinh ra va validator doi chieu.
    """
    match unit_original:
        case enums.TuitionUnit.DONG_NAM:
            return amount_original
        case enums.TuitionUnit.DONG_THANG:
            # Nam hoc = 10 thang (2 hoc ky chinh), khong tinh hoc ky he.
            return amount_original * 10
        case enums.TuitionUnit.DONG_TIN_CHI:
            if credits_per_year is None:
                raise ValueError(
                    "unit_original='dong_tin_chi' bat buoc co credits_per_year_assumed"
                )
            return amount_original * credits_per_year
        case enums.TuitionUnit.DONG_TOAN_KHOA:
            # amount_original = hoc phi CA KHOA (truong cong bo tron goi, on
            # dinh toan khoa). Chia deu cho so nam dao tao — xap xi, khong
            # phai muc tung nam truong cong bo rieng => luon needs_review
            # (xem TuitionRow._danh_dau_can_review).
            if duration_years is None:
                raise ValueError(
                    "unit_original='dong_toan_khoa' bat buoc co duration_years_assumed"
                )
            return round(Decimal(amount_original) / duration_years)


class Evidence(BaseModel):
    """Bang chung cho 1 con so. Khong co cai nay thi khong co record."""

    model_config = {"extra": "forbid"}

    quote: str = Field(min_length=10, max_length=2000)
    """Cau trich NGUYEN VAN tu tai lieu, con nguyen con so. Khong dien giai."""

    page: int | None = Field(default=None, ge=1)
    """So trang trong PDF (1-indexed). None = nguon HTML."""


class TuitionRow(BaseModel):
    """1 dong JSONL = 1 muc hoc phi cua 1 chuong trinh trong 1 nam hoc."""

    model_config = {"extra": "forbid"}

    # ── Dinh danh chuong trinh (de tim/tao `programs`) ───────────────────────
    school_slug: str
    """Khop `schools.slug` trong seeds/001_schools.sql."""

    major_slug: str | None = None
    """None = chua map duoc vao danh muc `majors` => needs_review."""

    major_name_raw: str = Field(min_length=2)
    """Ten nganh y nguyen nhu trong tai lieu — de nguoi duyet doi chieu."""

    track: enums.ProgramTrack
    language: Literal["vi", "en", "vi_en"] = "vi"
    campus: str | None = None
    """None = co so chinh."""

    # ── So lieu ─────────────────────────────────────────────────────────────
    academic_year: str
    """Dang "YYYY-YYYY", 2 nam lien tiep."""

    amount_original: int = Field(gt=0)
    """So Y NGUYEN nhu tai lieu cong bo."""

    unit_original: enums.TuitionUnit
    credits_per_year_assumed: int | None = Field(default=None, gt=0, le=100)
    duration_years_assumed: Decimal | None = Field(default=None, gt=0, le=10)
    """Ho tro .5 nam (7/9 hoc ky) — vd 3.5, 4.5. Xem Numeric(3,1) o app/models.py."""

    amount_per_year: int = Field(gt=0)
    """Dong/nam sau quy doi. Validator ep = quy_doi_ve_dong_nam(...)."""

    is_projected: bool = False
    """False = so truong cong bo. True = du phong theo % tang."""

    confidence: enums.ConfidenceLevel

    # ── Nguon ───────────────────────────────────────────────────────────────
    source_url: str = Field(min_length=8)
    source_doc_type: enums.SourceDocType
    source_published_date: date | None = None
    fetched_at: datetime
    evidence: Evidence

    # ── Kiem soat chat luong ────────────────────────────────────────────────
    needs_review: bool = False
    review_reason: str | None = None

    @model_validator(mode="after")
    def _kiem_tra(self) -> TuitionRow:
        self._kiem_academic_year()
        self._kiem_quy_doi()
        self._danh_dau_can_review()
        return self

    def _kiem_academic_year(self) -> None:
        if not ACADEMIC_YEAR_RE.match(self.academic_year):
            raise ValueError(
                f"academic_year phai dang YYYY-YYYY: {self.academic_year!r}"
            )
        dau, cuoi = self.academic_year.split("-")
        if int(cuoi) != int(dau) + 1:
            raise ValueError(
                f"academic_year phai la 2 nam lien tiep: {self.academic_year!r}"
            )

    def _kiem_quy_doi(self) -> None:
        """Ep amount_per_year = ket qua quy doi. Lech => model tu tinh => loi."""
        mong_doi = quy_doi_ve_dong_nam(
            self.amount_original,
            self.unit_original,
            self.credits_per_year_assumed,
            self.duration_years_assumed,
        )
        if self.amount_per_year != mong_doi:
            raise ValueError(
                f"amount_per_year={self.amount_per_year:,} khong khop quy doi "
                f"({self.amount_original:,} {self.unit_original.value} "
                f"=> {mong_doi:,}). Khong duoc tu tinh — de code quy doi."
            )

    def _danh_dau_can_review(self) -> None:
        """Bat cac dau hieu dang ngo. Khong nem loi — day sang nguoi duyet."""
        ly_do: list[str] = []
        if not (MIN_PER_YEAR <= self.amount_per_year <= MAX_PER_YEAR):
            ly_do.append(
                f"amount_per_year={self.amount_per_year:,} ngoai bien do "
                f"[{MIN_PER_YEAR:,}..{MAX_PER_YEAR:,}]"
            )
        if self.major_slug is None:
            ly_do.append(f"chua map duoc nganh {self.major_name_raw!r} vao danh muc")
        if (
            self.unit_original is enums.TuitionUnit.DONG_TIN_CHI
            and self.credits_per_year_assumed == DEFAULT_CREDITS_PER_YEAR
        ):
            ly_do.append("so tin chi/nam la gia dinh mac dinh, khong phai so cong bo")
        if self.unit_original is enums.TuitionUnit.DONG_TOAN_KHOA:
            ly_do.append(
                "amount_per_year suy ra tu hoc phi toan khoa / so nam dao tao (gia "
                "dinh chia deu theo nam) — khong phai muc tung nam truong cong bo rieng"
            )
        if self.confidence is enums.ConfidenceLevel.ESTIMATED:
            ly_do.append("confidence=estimated")

        if ly_do:
            self.needs_review = True
            cu = f"{self.review_reason}; " if self.review_reason else ""
            self.review_reason = cu + "; ".join(ly_do)
