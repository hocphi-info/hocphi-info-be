"""Pydantic response model dung chung o nhieu router (majors/schools/detail).

Tach khoi `app/models.py` (ORM) — day la lop DTO rieng, "lap" tay tu ket qua
query (join nhieu bang) chu khong tra thang ORM object. `CamelModel` tu sinh
alias camelCase tu ten field snake_case (`alias_generator=to_camel`), khong
can viet tay `Field(alias=...)` moi field. `hocphi-info-fe/src/types/domain.ts`
la "hop dong" — moi field o day PHAI khop ten + kieu ben do.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SchoolOut(CamelModel):
    """Khop `School` domain.ts."""

    slug: str
    name: str
    short_name: str | None
    city_code: str
    category: str
    # URL logo truong (schools.logo_url) — NULL = chua co; FE hien chu viet tat.
    logo_url: str | None = None


class MajorOut(CamelModel):
    """Khop `Major` domain.ts."""

    slug: str
    name: str
    code: str | None
    group_code: str
    standard_years: int
    requires_practice_license: bool
    practice_profession: str | None


class ProgramOut(CamelModel):
    """Khop `Program` domain.ts — FE dung slug cho school/major, BE dung FK
    (join luc build response, khong doi cot DB)."""

    id: str
    school_slug: str
    major_slug: str
    track: str
    language: str
    # NULL = co so chinh. Chuoi tu do (vd "Khánh Hòa") khi la phan hieu/co so khac.
    campus: str | None = None
    # Ten hien thi rieng cua chuong trinh khi lech ten `majors` dung chung
    # (vd chuyen nganh) — NULL thi UI dung `majors.name`. Xem docs/schema.md.
    display_name: str | None = None


class SourceOut(CamelModel):
    """Khop `Source` domain.ts (F12) — chi gan duoc voi ban ghi CONG BO that
    (Nam 1); cac nam du phong la so tinh, khong co source_id that."""

    url: str
    doc_type: str
    published_date: date | None


class TuitionRecordOut(CamelModel):
    """Khop `TuitionRecord` domain.ts. KHONG lo needs_review/review_reason —
    chua co UI hien thi (xem migration 0002 + plan Tuan 2)."""

    program_id: str
    academic_year: str
    amount_per_year: int
    is_projected: bool
    confidence: str
    source: SourceOut | None = None


class ProgramIncreaseOut(CamelModel):
    """Khop `ProgramIncrease` domain.ts."""

    program_id: str
    annual_increase_pct: float
    increase_source: str


class MajorRowOut(CamelModel):
    """Khop `MajorRow` domain.ts — 1 dong o man hinh S1 (`GET /api/majors`)."""

    program: ProgramOut
    school: SchoolOut
    major: MajorOut
    year1: TuitionRecordOut
    increase: ProgramIncreaseOut | None


class SchoolStatsOut(CamelModel):
    """Khop `SchoolStats` domain.ts."""

    n_programs: int
    min_amount: int
    min_major_name: str
    median_amount: float
    max_amount: int
    max_major_name: str
    increase_summary: str


class SchoolRowOut(CamelModel):
    """Khop `SchoolRow` domain.ts — 1 dong o man hinh S2 (`GET /api/schools`)."""

    school: SchoolOut
    stats: SchoolStatsOut


class SchoolTrackStatOut(CamelModel):
    """Khop `SchoolTrackStat` domain.ts — 1 hang / he dao tao trong 1 truong
    (F7 chart Min-Max noi bo truong). Cung VIEW `school_track_stats` voi
    SchoolStatsOut nhung loc theo school_id thay vi track — moi truong co toi
    da 1 dong / he da co chuong trinh."""

    track: str
    n_programs: int
    min_amount: int
    min_major_name: str
    median_amount: float
    max_amount: int
    max_major_name: str


class SchoolProgramRowOut(CamelModel):
    """Khop `SchoolProgramRow` domain.ts — 1 dong trong bang danh sach nganh
    cua 1 truong (F7). `year1.source` luon None o day — F12 (nguon) chi hien
    o trang F6, khong lap lai o F7 (xem plan Tuan 4)."""

    program: ProgramOut
    major: MajorOut
    year1: TuitionRecordOut


class SchoolDetailResponseOut(CamelModel):
    """Khop response cua `GET /api/schools/{school_slug}` (F7)."""

    school: SchoolOut
    track_stats: list[SchoolTrackStatOut]
    programs: list[SchoolProgramRowOut]


class YearlyAmountOut(CamelModel):
    """1 nam trong bang hoc phi tinh luy tien cua 1 program (S3) — so **tinh**,
    khong phai ban ghi DB (khac TuitionRecordOut: khong co program_id/confidence)."""

    academic_year: str
    amount_per_year: int
    is_projected: bool


class ProgramDetailOut(CamelModel):
    """1 he dao tao (track/language/campus) trong trang chi tiet nganh-truong (S3)."""

    program: ProgramOut
    year1: TuitionRecordOut
    increase: ProgramIncreaseOut | None
    yearly_amounts: list[YearlyAmountOut]
    total_course: int
    total_with_license: int


class ProgramDetailResponseOut(CamelModel):
    """Khop response cua `GET /api/schools/{school_slug}/majors/{major_slug}` (S3) —
    gom TAT CA programs cung (school, major), dung schema.md §3."""

    school: SchoolOut
    major: MajorOut
    programs: list[ProgramDetailOut]
