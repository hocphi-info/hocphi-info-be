"""Tat ca model SQLAlchemy — 1 file (MVP 11 bang). Ban dich 1-1 cua `docs/schema.md`
v0.2 §2-§3 sang Python.

Doc theo thu tu: TimestampSoftDelete (quy uoc chung) -> City/MajorGroup/AppSetting
(bang tra cuu, khong ULID/soft-delete) -> School/Major/Program/... (bang nghiep vu).

Kieu Mapped[] + mapped_column() la style native-typed cua SQLAlchemy 2.x — mypy
hieu truc tiep, KHONG can plugin. Tuong duong: struct + tag ORM cua gorm (Go),
model class + ORM cua drift (Flutter).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import enums
from app.db import Base

# ── Helper: ENUM Postgres dung lai type da tao trong migration ────────────────
# create_type=False -> SQLAlchemy KHONG tu CREATE TYPE (migration 0001 lo viec do).
# values_callable -> luu GIA TRI cua enum ('cong_lap') chu khong TEN thanh vien
# ('CONG_LAP'). Quan trong: FE (domain.ts) va query Tuan 2 xai dung gia tri nay.


def _pg_enum(py_enum: type, name: str) -> PgEnum:
    return PgEnum(
        py_enum,
        name=name,
        create_type=False,
        values_callable=lambda e: [member.value for member in e],
    )


# ── Quy uoc chung cho bang nghiep vu (schema.md §3) ──────────────────────────
class TimestampSoftDelete:
    """Mixin: id ULID sinh o DB + created_at/updated_at + deleted_at (soft delete).

    `cities`, `major_groups`, `app_settings` KHONG dung mixin nay (bang tra cuu
    tinh khoa bang code/key).
    """

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("gen_ulid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    # NULL = con song; co gia tri = da xoa mem. Query mac dinh loc IS NULL.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── Bang tra cuu (khoa = code/key, khong ULID, khong soft-delete) ────────────
class City(Base):
    __tablename__ = "cities"

    code: Mapped[str] = mapped_column(Text, primary_key=True)  # HCM, HN
    name: Mapped[str] = mapped_column(Text, nullable=False)

    schools: Mapped[list[School]] = relationship(back_populates="city")


class MajorGroup(Base):
    __tablename__ = "major_groups"

    code: Mapped[str] = mapped_column(Text, primary_key=True)  # CNTT, KY_THUAT...
    name: Mapped[str] = mapped_column(Text, nullable=False)

    majors: Mapped[list[Major]] = relationship(back_populates="group")


class AppSetting(Base):
    """Cau hinh dan xuat (schema.md §3): current_intake_year, course_years_default,
    default_increase_pct, default_increase_band_pct. Value luu dang text, tang API
    tu ep kieu khi doc."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── Bang nghiep vu ──────────────────────────────────────────────────────────
class School(Base, TimestampSoftDelete):
    __tablename__ = "schools"
    __table_args__ = (
        # Partial unique: cho phep tao lai slug sau khi ban ghi cu da xoa mem.
        Index(
            "uq_schools_slug",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)  # khoa URL cong khai
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    city_code: Mapped[str] = mapped_column(
        Text, ForeignKey("cities.code"), nullable=False
    )
    category: Mapped[enums.SchoolCategory] = mapped_column(
        _pg_enum(enums.SchoolCategory, enums.SCHOOL_CATEGORY), nullable=False
    )
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    city: Mapped[City] = relationship(back_populates="schools")
    programs: Mapped[list[Program]] = relationship(back_populates="school")


class Major(Base, TimestampSoftDelete):
    __tablename__ = "majors"
    __table_args__ = (
        Index(
            "uq_majors_slug",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "standard_years BETWEEN 3 AND 7",
            name="ck_majors_standard_years",
        ),
        # requires_practice_license = true => practice_profession phai co.
        CheckConstraint(
            "NOT requires_practice_license OR practice_profession IS NOT NULL",
            name="ck_majors_practice_profession",
        ),
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Ma nganh cap IV — KHONG unique (nhieu truong trung ma), nullable (nganh moi).
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_code: Mapped[str] = mapped_column(
        Text, ForeignKey("major_groups.code"), nullable=False
    )
    # So nam chuan cua khoa — may tinh total_course dung lam `years` mac dinh.
    standard_years: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("4")
    )
    requires_practice_license: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    practice_profession: Mapped[str | None] = mapped_column(Text, nullable=True)

    group: Mapped[MajorGroup] = relationship(back_populates="majors")
    programs: Mapped[list[Program]] = relationship(back_populates="major")
    post_grad_requirements: Mapped[list[PostGradRequirement]] = relationship(
        back_populates="major"
    )


class Program(Base, TimestampSoftDelete):
    """Don vi nho nhat co 1 muc hoc phi = truong x nganh x he x ngon ngu x co so."""

    __tablename__ = "programs"
    __table_args__ = (
        # UNIQUE (school, major, track, language, COALESCE(campus,'')) — partial.
        Index(
            "uq_programs_combo",
            "school_id",
            "major_id",
            "track",
            "language",
            text("COALESCE(campus, '')"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "language IN ('vi', 'en', 'vi_en')",
            name="ck_programs_language",
        ),
    )

    school_id: Mapped[str] = mapped_column(
        Text, ForeignKey("schools.id"), nullable=False
    )
    major_id: Mapped[str] = mapped_column(Text, ForeignKey("majors.id"), nullable=False)
    track: Mapped[enums.ProgramTrack] = mapped_column(
        _pg_enum(enums.ProgramTrack, enums.PROGRAM_TRACK), nullable=False
    )
    # `text` chu khong ENUM (schema.md §2) — CHECK o __table_args__ giu hop le.
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    # NULL = co so chinh.
    campus: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    school: Mapped[School] = relationship(back_populates="programs")
    major: Mapped[Major] = relationship(back_populates="programs")
    tuition_records: Mapped[list[TuitionRecord]] = relationship(
        back_populates="program"
    )
    increase: Mapped[ProgramIncrease | None] = relationship(
        back_populates="program", uselist=False
    )


class Source(Base, TimestampSoftDelete):
    """Tai lieu goc — dung chung cho tuition_records, program_increase, post_grad."""

    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[enums.SourceDocType] = mapped_column(
        _pg_enum(enums.SourceDocType, enums.SOURCE_DOC_TYPE), nullable=False
    )
    page_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TuitionRecord(Base, TimestampSoftDelete):
    """1 muc hoc phi / chuong trinh / nam hoc."""

    __tablename__ = "tuition_records"
    __table_args__ = (
        Index(
            "uq_tuition_program_year",
            "program_id",
            "academic_year",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # academic_year dang "YYYY-YYYY", 2 nam lien tiep.
        CheckConstraint(
            "academic_year ~ '^[0-9]{4}-[0-9]{4}$' "
            "AND CAST(right(academic_year, 4) AS integer) "
            "= CAST(left(academic_year, 4) AS integer) + 1",
            name="ck_tuition_academic_year_format",
        ),
        # unit_original = 'dong_tin_chi' => phai co credits_per_year_assumed.
        CheckConstraint(
            "unit_original <> 'dong_tin_chi' OR credits_per_year_assumed IS NOT NULL",
            name="ck_tuition_credits_when_per_credit",
        ),
        # unit_original = 'dong_toan_khoa' => phai co duration_years_assumed.
        CheckConstraint(
            "unit_original <> 'dong_toan_khoa' OR duration_years_assumed IS NOT NULL",
            name="ck_tuition_duration_when_toan_khoa",
        ),
        # confidence = 'verified' => phai co source_id + verified_at.
        CheckConstraint(
            "confidence <> 'verified' "
            "OR (source_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_tuition_verified_needs_source",
        ),
    )

    program_id: Mapped[str] = mapped_column(
        Text, ForeignKey("programs.id"), nullable=False
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)  # "2026-2027"
    # Cot generated — de loc / sap xep theo nam bat dau.
    academic_year_start: Mapped[int] = mapped_column(
        SmallInteger,
        Computed("CAST(left(academic_year, 4) AS smallint)", persisted=True),
    )
    amount_per_year: Mapped[int] = mapped_column(BigInteger, nullable=False)  # dong/nam
    unit_original: Mapped[enums.TuitionUnit] = mapped_column(
        _pg_enum(enums.TuitionUnit, enums.TUITION_UNIT), nullable=False
    )
    amount_original: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credits_per_year_assumed: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    # Numeric (khong phai smallint) — mot so truong dung khoa 3,5/4,5 nam
    # (7/9 hoc ky) thay vi so nam tron (vd HUTECH: Dieu duong 3,5 nam).
    duration_years_assumed: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1), nullable=True
    )
    is_projected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    confidence: Mapped[enums.ConfidenceLevel] = mapped_column(
        _pg_enum(enums.ConfidenceLevel, enums.CONFIDENCE_LEVEL), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    verified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Trang thai duyet cua AI-crawler (migration 0002) — giu nguyen tu
    # seeds/*.jsonl, KHONG lo ra response API o Tuan 2 (chi tra soat truc tiep DB).
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[Program] = relationship(back_populates="tuition_records")


class ProgramIncrease(Base):
    """% tang hoc phi/nam — 1-1 voi programs. PK = FK program_id (khong co id ULID
    rieng), nen KHONG dung mixin TimestampSoftDelete — khai timestamp truc tiep."""

    __tablename__ = "program_increase"
    __table_args__ = (
        # published_roadmap => phai co source_id.
        CheckConstraint(
            "increase_source <> 'published_roadmap' OR source_id IS NOT NULL",
            name="ck_increase_roadmap_needs_source",
        ),
    )

    program_id: Mapped[str] = mapped_column(
        Text, ForeignKey("programs.id"), primary_key=True
    )
    annual_increase_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    increase_source: Mapped[enums.IncreaseSourceKind] = mapped_column(
        _pg_enum(enums.IncreaseSourceKind, enums.INCREASE_SOURCE_KIND), nullable=False
    )
    roadmap_years_known: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    program: Mapped[Program] = relationship(back_populates="increase")


class PostGradRequirement(Base, TimestampSoftDelete):
    """Chi phi hanh nghe — gan theo NGANH (khong theo program)."""

    __tablename__ = "post_grad_requirements"
    __table_args__ = (
        Index(
            "uq_postgrad_major_step",
            "major_id",
            "step_order",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("cost_max >= cost_min", name="ck_postgrad_cost_range"),
    )

    major_id: Mapped[str] = mapped_column(Text, ForeignKey("majors.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_months: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cost_min: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_max: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confidence: Mapped[enums.ConfidenceLevel] = mapped_column(
        _pg_enum(enums.ConfidenceLevel, enums.CONFIDENCE_LEVEL),
        nullable=False,
        server_default=text("'estimated'"),
    )
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    source_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )

    major: Mapped[Major] = relationship(back_populates="post_grad_requirements")
