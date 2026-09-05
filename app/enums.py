"""Python enum <-> ENUM Postgres.

`schema.md` §1.6: dung ENUM cho bo gia tri on dinh (he dao tao, do tin cay, loai
tai lieu...). O Python dung `enum.StrEnum` — moi thanh vien vua la enum vua la str,
nen so sanh voi chuoi tu JSON/DB thang duoc (giong `iota` const + type cua Go, hoac
`enum` + `@JsonValue` cua Dart).

Ten type Postgres (tham so `name=...` khi khai bao cot) phai khop hang so ky o day
va lenh CREATE TYPE trong migration 0001.
"""

from enum import StrEnum

# Ten type ENUM Postgres — dung o ca app/models.py va alembic/versions/0001.
# `language` cua programs la `text` (schema.md §2 ERD: "vi | en | vi_en"), KHONG
# phai ENUM — dung String + CHECK, xem ProgramLanguage ben duoi.
SCHOOL_CATEGORY = "school_category"
PROGRAM_TRACK = "program_track"
TUITION_UNIT = "tuition_unit"
CONFIDENCE_LEVEL = "confidence_level"
INCREASE_SOURCE_KIND = "increase_source_kind"
SOURCE_DOC_TYPE = "source_doc_type"

# Tat ca ten type ENUM — migration 0001 lap qua day de CREATE/DROP.
ALL_ENUM_TYPES = (
    SCHOOL_CATEGORY,
    PROGRAM_TRACK,
    TUITION_UNIT,
    CONFIDENCE_LEVEL,
    INCREASE_SOURCE_KIND,
    SOURCE_DOC_TYPE,
)


class SchoolCategory(StrEnum):
    """Gop `type` + `autonomy_status` cua brief thanh 1 enum (schema.md §3 schools)."""

    CONG_LAP = "cong_lap"
    CONG_LAP_TU_CHU = "cong_lap_tu_chu"
    TU_THUC = "tu_thuc"
    # RMIT — tach rieng de loai khoi phep trung vi dai tra.
    TU_THUC_VON_NUOC_NGOAI = "tu_thuc_von_nuoc_ngoai"


class ProgramTrack(StrEnum):
    """He dao tao — hoc phi chenh 3-5 lan, khong bao gio tron khi tinh trung vi."""

    DAI_TRA = "dai_tra"
    CHAT_LUONG_CAO = "chat_luong_cao"
    TIEN_TIEN = "tien_tien"
    QUOC_TE = "quoc_te"


class ProgramLanguage(StrEnum):
    """Cot `programs.language` la `text` (schema.md §2), khong phai ENUM — nhung
    van dung enum nay lam kieu Python + nguon cho CHECK constraint."""

    VI = "vi"
    EN = "en"
    VI_EN = "vi_en"


class TuitionUnit(StrEnum):
    """Don vi goc truong cong bo — giu de doi chieu khi tranh chap so lieu."""

    DONG_NAM = "dong_nam"
    DONG_THANG = "dong_thang"
    DONG_TIN_CHI = "dong_tin_chi"  # bat buoc credits_per_year_assumed (CHECK)


class ConfidenceLevel(StrEnum):
    VERIFIED = "verified"  # bat buoc source_id + verified_at (CHECK)
    PUBLISHED_UNVERIFIED = "published_unverified"
    ESTIMATED = "estimated"


class IncreaseSourceKind(StrEnum):
    PUBLISHED_ROADMAP = "published_roadmap"  # bat buoc source_id (CHECK)
    DEFAULT_ESTIMATE = "default_estimate"  # dung app_settings.default_increase_pct


class SourceDocType(StrEnum):
    DE_AN_TUYEN_SINH = "de_an_tuyen_sinh"
    THONG_BAO_HOC_PHI = "thong_bao_hoc_phi"
    QUY_DINH_NGHE = "quy_dinh_nghe"
    KHAC = "khac"

