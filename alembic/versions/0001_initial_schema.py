"""initial schema — hocphi.info v0.2

Migration KHOI TAO, viet tay phan dau/cuoi, than create_table sinh boi
`alembic revision --autogenerate` roi chinh (schema.md v0.2).

Thu tu upgrade() (= thu tu Postgres dung schema):
  1. CREATE EXTENSION pgcrypto        — gen_random_bytes() cho gen_ulid()
  2. CREATE FUNCTION gen_ulid()       — ULID 26 ky tu, sinh o DB (geckoboard/pgulid)
  3. CREATE FUNCTION set_updated_at() + CREATE TYPE ... ENUM x7
  4. op.create_table x10              — kem Computed, named CHECK, partial unique index
  5. trigger set_updated_at cho moi bang co cot updated_at
  6. CREATE VIEW school_track_stats   — Min-Max/trung vi/so nganh theo (truong, he) (schema.md §4)
  7. seed cities / major_groups / app_settings (schema.md §3)

downgrade() dao nguoc: drop view -> drop table -> drop type -> drop function -> drop extension.

Revision ID: 0001
Revises:
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Ham gen_ulid() — geckoboard/pgulid (Apache-2.0), doi ten generate_ulid -> gen_ulid ──
# https://github.com/geckoboard/pgulid — 6 byte timestamp + 10 byte entropy, Crockford base32.
# Han che da biet: khong monotonic trong cung 1ms (2 ULID cung ms sap theo phan random).
GEN_ULID_SQL = r"""
CREATE FUNCTION gen_ulid()
RETURNS TEXT
AS $$
DECLARE
  encoding   BYTEA = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  timestamp  BYTEA = E'\\000\\000\\000\\000\\000\\000';
  output     TEXT = '';
  unix_time  BIGINT;
  ulid       BYTEA;
BEGIN
  unix_time = (EXTRACT(EPOCH FROM CLOCK_TIMESTAMP()) * 1000)::BIGINT;
  timestamp = SET_BYTE(timestamp, 0, (unix_time >> 40)::BIT(8)::INTEGER);
  timestamp = SET_BYTE(timestamp, 1, (unix_time >> 32)::BIT(8)::INTEGER);
  timestamp = SET_BYTE(timestamp, 2, (unix_time >> 24)::BIT(8)::INTEGER);
  timestamp = SET_BYTE(timestamp, 3, (unix_time >> 16)::BIT(8)::INTEGER);
  timestamp = SET_BYTE(timestamp, 4, (unix_time >> 8)::BIT(8)::INTEGER);
  timestamp = SET_BYTE(timestamp, 5, unix_time::BIT(8)::INTEGER);

  ulid = timestamp || gen_random_bytes(10);

  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 0) & 224) >> 5));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 0) & 31)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 1) & 248) >> 3));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 1) & 7) << 2) | ((GET_BYTE(ulid, 2) & 192) >> 6)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 2) & 62) >> 1));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 2) & 1) << 4) | ((GET_BYTE(ulid, 3) & 240) >> 4)));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 3) & 15) << 1) | ((GET_BYTE(ulid, 4) & 128) >> 7)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 4) & 124) >> 2));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 4) & 3) << 3) | ((GET_BYTE(ulid, 5) & 224) >> 5)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 5) & 31)));

  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 6) & 248) >> 3));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 6) & 7) << 2) | ((GET_BYTE(ulid, 7) & 192) >> 6)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 7) & 62) >> 1));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 7) & 1) << 4) | ((GET_BYTE(ulid, 8) & 240) >> 4)));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 8) & 15) << 1) | ((GET_BYTE(ulid, 9) & 128) >> 7)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 9) & 124) >> 2));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 9) & 3) << 3) | ((GET_BYTE(ulid, 10) & 224) >> 5)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 10) & 31)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 11) & 248) >> 3));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 11) & 7) << 2) | ((GET_BYTE(ulid, 12) & 192) >> 6)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 12) & 62) >> 1));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 12) & 1) << 4) | ((GET_BYTE(ulid, 13) & 240) >> 4)));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 13) & 15) << 1) | ((GET_BYTE(ulid, 14) & 128) >> 7)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 14) & 124) >> 2));
  output = output || CHR(GET_BYTE(encoding, ((GET_BYTE(ulid, 14) & 3) << 3) | ((GET_BYTE(ulid, 15) & 224) >> 5)));
  output = output || CHR(GET_BYTE(encoding, (GET_BYTE(ulid, 15) & 31)));

  RETURN output;
END
$$
LANGUAGE plpgsql
VOLATILE;
"""

# Trigger cap nhat updated_at moi lan UPDATE (schema.md §3).
SET_UPDATED_AT_SQL = """
CREATE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END
$$ LANGUAGE plpgsql;
"""

# (ten type, [gia tri]) — gia tri LOWERCASE khop enum.value ben app/enums.py.
ENUM_TYPES: list[tuple[str, list[str]]] = [
    (
        "school_category",
        ["cong_lap", "cong_lap_tu_chu", "tu_thuc", "tu_thuc_von_nuoc_ngoai"],
    ),
    ("program_track", ["dai_tra", "chat_luong_cao", "tien_tien", "quoc_te"]),
    ("tuition_unit", ["dong_nam", "dong_thang", "dong_tin_chi"]),
    ("confidence_level", ["verified", "published_unverified", "estimated"]),
    ("increase_source_kind", ["published_roadmap", "default_estimate"]),
    (
        "source_doc_type",
        ["de_an_tuyen_sinh", "thong_bao_hoc_phi", "quy_dinh_nghe", "khac"],
    ),
]

# Bang co cot updated_at -> gan trigger set_updated_at.
TABLES_WITH_UPDATED_AT = [
    "schools",
    "majors",
    "programs",
    "sources",
    "tuition_records",
    "program_increase",
    "post_grad_requirements",
]

# VIEW S2 (schema.md §4): Min-Max / trung vi / so nganh cho moi (school, track),
# dua tren so hoc phi CONG BO moi nhat (is_projected = false, nam hoc lon nhat) cua
# tung program. Khong tron he. Min/Max kem major_id de UI hien ten nganh.
SCHOOL_TRACK_STATS_VIEW = """
CREATE VIEW school_track_stats AS
WITH latest AS (
    SELECT DISTINCT ON (tr.program_id)
        tr.program_id,
        tr.amount_per_year,
        p.school_id,
        p.major_id,
        p.track
    FROM tuition_records tr
    JOIN programs p ON p.id = tr.program_id AND p.deleted_at IS NULL
    WHERE tr.deleted_at IS NULL
      AND tr.is_projected = false
    ORDER BY tr.program_id, tr.academic_year_start DESC
),
ranked AS (
    SELECT
        school_id,
        track,
        amount_per_year,
        major_id,
        MIN(amount_per_year) OVER (PARTITION BY school_id, track) AS min_amount,
        MAX(amount_per_year) OVER (PARTITION BY school_id, track) AS max_amount
    FROM latest
)
SELECT
    l.school_id,
    l.track,
    COUNT(*) AS n_programs,
    MIN(l.amount_per_year) AS min_amount,
    MAX(l.amount_per_year) AS max_amount,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.amount_per_year) AS median_amount,
    (SELECT r.major_id FROM ranked r
     WHERE r.school_id = l.school_id AND r.track = l.track
       AND r.amount_per_year = r.min_amount
     LIMIT 1) AS min_major_id,
    (SELECT r.major_id FROM ranked r
     WHERE r.school_id = l.school_id AND r.track = l.track
       AND r.amount_per_year = r.max_amount
     LIMIT 1) AS max_major_id
FROM latest l
GROUP BY l.school_id, l.track;
"""


def _enum(name: str) -> postgresql.ENUM:
    """ENUM da tao san (create_type=False) — dung trong create_table."""
    values = next(v for n, v in ENUM_TYPES if n == name)
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    # 1-2. Extension + ham sinh ULID.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(GEN_ULID_SQL)
    # 3. Trigger fn + cac type ENUM.
    op.execute(SET_UPDATED_AT_SQL)
    for name, values in ENUM_TYPES:
        vals = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({vals})")

    # 4. Bang (than sinh boi autogenerate, chinh ENUM sang _enum(...) + doc lai).
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "cities",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "major_groups",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "sources",
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("doc_type", _enum("source_doc_type"), nullable=False),
        sa.Column("page_ref", sa.Text(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_by", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "majors",
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("group_code", sa.Text(), nullable=False),
        sa.Column(
            "standard_years",
            sa.SmallInteger(),
            server_default=sa.text("4"),
            nullable=False,
        ),
        sa.Column(
            "requires_practice_license",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("practice_profession", sa.Text(), nullable=True),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "NOT requires_practice_license OR practice_profession IS NOT NULL",
            name="ck_majors_practice_profession",
        ),
        sa.CheckConstraint(
            "standard_years BETWEEN 3 AND 7", name="ck_majors_standard_years"
        ),
        sa.ForeignKeyConstraint(["group_code"], ["major_groups.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_majors_slug",
        "majors",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "schools",
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("city_code", sa.Text(), nullable=False),
        sa.Column("category", _enum("school_category"), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["city_code"], ["cities.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_schools_slug",
        "schools",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "post_grad_requirements",
        sa.Column("major_id", sa.Text(), nullable=False),
        sa.Column("step_order", sa.SmallInteger(), nullable=False),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("duration_months", sa.SmallInteger(), nullable=True),
        sa.Column("cost_min", sa.BigInteger(), nullable=False),
        sa.Column("cost_max", sa.BigInteger(), nullable=False),
        sa.Column(
            "confidence",
            _enum("confidence_level"),
            server_default=sa.text("'estimated'"),
            nullable=False,
        ),
        sa.Column(
            "verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("cost_max >= cost_min", name="ck_postgrad_cost_range"),
        sa.ForeignKeyConstraint(["major_id"], ["majors.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_postgrad_major_step",
        "post_grad_requirements",
        ["major_id", "step_order"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "programs",
        sa.Column("school_id", sa.Text(), nullable=False),
        sa.Column("major_id", sa.Text(), nullable=False),
        sa.Column("track", _enum("program_track"), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("campus", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "language IN ('vi', 'en', 'vi_en')", name="ck_programs_language"
        ),
        sa.ForeignKeyConstraint(["major_id"], ["majors.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_programs_combo",
        "programs",
        [
            "school_id",
            "major_id",
            "track",
            "language",
            sa.literal_column("COALESCE(campus, '')"),
        ],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "program_increase",
        sa.Column("program_id", sa.Text(), nullable=False),
        sa.Column(
            "annual_increase_pct", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column("increase_source", _enum("increase_source_kind"), nullable=False),
        sa.Column("roadmap_years_known", sa.SmallInteger(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "increase_source <> 'published_roadmap' OR source_id IS NOT NULL",
            name="ck_increase_roadmap_needs_source",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("program_id"),
    )
    op.create_table(
        "tuition_records",
        sa.Column("program_id", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column(
            "academic_year_start",
            sa.SmallInteger(),
            sa.Computed("CAST(left(academic_year, 4) AS smallint)", persisted=True),
            nullable=False,
        ),
        sa.Column("amount_per_year", sa.BigInteger(), nullable=False),
        sa.Column("unit_original", _enum("tuition_unit"), nullable=False),
        sa.Column("amount_original", sa.BigInteger(), nullable=False),
        sa.Column("credits_per_year_assumed", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_projected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("confidence", _enum("confidence_level"), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_ulid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "academic_year ~ '^[0-9]{4}-[0-9]{4}$' "
            "AND CAST(right(academic_year, 4) AS integer) "
            "= CAST(left(academic_year, 4) AS integer) + 1",
            name="ck_tuition_academic_year_format",
        ),
        sa.CheckConstraint(
            "confidence <> 'verified' "
            "OR (source_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_tuition_verified_needs_source",
        ),
        sa.CheckConstraint(
            "unit_original <> 'dong_tin_chi' OR credits_per_year_assumed IS NOT NULL",
            name="ck_tuition_credits_when_per_credit",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_tuition_program_year",
        "tuition_records",
        ["program_id", "academic_year"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 5. Trigger updated_at cho moi bang nghiep vu.
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"CREATE TRIGGER trg_{table}_set_updated_at "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    # 6. VIEW S2.
    op.execute(SCHOOL_TRACK_STATS_VIEW)

    # 7. Seed bang tra cuu (schema.md §3).
    op.bulk_insert(
        sa.table(
            "cities",
            sa.column("code", sa.Text),
            sa.column("name", sa.Text),
        ),
        [
            {"code": "HCM", "name": "TP. Ho Chi Minh"},
            {"code": "HN", "name": "Ha Noi"},
        ],
    )
    op.bulk_insert(
        sa.table(
            "major_groups",
            sa.column("code", sa.Text),
            sa.column("name", sa.Text),
        ),
        [
            {"code": "CNTT", "name": "Cong nghe thong tin"},
            {"code": "KY_THUAT", "name": "Ky thuat"},
            {"code": "KINH_TE", "name": "Kinh te - Tai chinh - Quan tri"},
            {"code": "Y_DUOC", "name": "Y - Duoc"},
            {"code": "LUAT", "name": "Luat"},
            {"code": "LOGISTICS", "name": "Logistics & Quan ly chuoi cung ung"},
        ],
    )
    op.bulk_insert(
        sa.table(
            "app_settings",
            sa.column("key", sa.Text),
            sa.column("value", sa.Text),
            sa.column("description", sa.Text),
        ),
        [
            {
                "key": "current_intake_year",
                "value": "2026",
                "description": "Nam nhap hoc cua 'Nam dau' dang hien thi",
            },
            {
                "key": "course_years_default",
                "value": "4",
                "description": "So nam khoa cu nhan mac dinh (fallback cho standard_years)",
            },
            {
                "key": "default_increase_pct",
                "value": "10",
                "description": "% tang/nam khi truong khong cong bo lo trinh",
            },
            {
                "key": "default_increase_band_pct",
                "value": "3",
                "description": "Bien +/- cho khoang min-max khi dung uoc luong",
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema — dao nguoc thu tu upgrade()."""
    op.execute("DROP VIEW IF EXISTS school_track_stats")

    for table in TABLES_WITH_UPDATED_AT:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table}")

    op.drop_index(
        "uq_tuition_program_year",
        table_name="tuition_records",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("tuition_records")
    op.drop_table("program_increase")
    op.drop_index(
        "uq_programs_combo",
        table_name="programs",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("programs")
    op.drop_index(
        "uq_postgrad_major_step",
        table_name="post_grad_requirements",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("post_grad_requirements")
    op.drop_index(
        "uq_schools_slug",
        table_name="schools",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("schools")
    op.drop_index(
        "uq_majors_slug",
        table_name="majors",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("majors")
    op.drop_table("sources")
    op.drop_table("major_groups")
    op.drop_table("cities")
    op.drop_table("app_settings")

    for name, _ in ENUM_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS gen_ulid()")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
