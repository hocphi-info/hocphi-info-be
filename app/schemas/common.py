"""Pydantic response model dung chung o nhieu router (majors/schools/search).

Tach khoi `app/models.py` (ORM) — day la lop DTO rieng, "lap" tay tu ket qua
query (join nhieu bang) chu khong tra thang ORM object. `CamelModel` tu sinh
alias camelCase tu ten field snake_case (`alias_generator=to_camel`), khong
can viet tay `Field(alias=...)` moi field. `hocphi-info-fe/src/types/domain.ts`
la "hop dong" — moi field o day PHAI khop ten + kieu ben do.
"""

from __future__ import annotations

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


class TuitionRecordOut(CamelModel):
    """Khop `TuitionRecord` domain.ts. KHONG lo needs_review/review_reason —
    chua co UI hien thi (xem migration 0002 + plan Tuan 2)."""

    program_id: str
    academic_year: str
    amount_per_year: int
    is_projected: bool
    confidence: str


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


class SearchHitOut(CamelModel):
    """Khop `SearchHit` domain.ts — 1 goi y cua F13 (`GET /api/search?q=`)."""

    kind: str
    slug: str
    name: str
    short_name: str | None = None
