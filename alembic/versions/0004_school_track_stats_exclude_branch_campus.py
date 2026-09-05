"""school_track_stats: loai chuong trinh o PHAN HIEU (campus IS NOT NULL) khoi
thong ke khoang hoc phi "theo he"

Owner chot (2026-09-06, sau khi crawl TDTU): phan hieu vung (vd Phan hieu Khanh
Hoa cua TDTU) thu hoc phi thap hon han co so chinh — Du lich Nhom 1 la 20,5 tr o
Khanh Hoa vs 31,26 tr o co so chinh. VIEW `school_track_stats` (schema.md §4) gop
Min-Max/trung vi CHI theo (school, track) nen mot muc gia phan hieu se keo lech
con so headline o S2 (`/api/schools`) va F7 (`/api/schools/{slug}`), dung kieu
distortion ma nguyen tac "khong tron he" muon tranh (mo rong tu nhien sang "khong
tron co so").

Thay doi DUY NHAT: them `AND p.campus IS NULL` vao CTE `latest`. Chuong trinh
phan hieu VAN xuat hien trong danh sach `programs[]` cua F7 (query rieng, khong
qua VIEW) — kem nhan co so o UI.

Han che da biet: truong CHI co chuong trinh he do o phan hieu se khong xuat hien
o S2 / trackStats. Hom nay khong co case nao (TDTU con nhieu chuong trinh co so
chinh). Xem docs/schema.md §6.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Chi khac ban 0001 o 1 dong: "AND p.campus IS NULL" trong CTE `latest`.
_VIEW_WITH_CAMPUS_FILTER = """
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
      AND p.campus IS NULL
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

# Ban 0001 nguyen van (khong co dong campus) — dung cho downgrade.
_VIEW_0001 = """
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


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS school_track_stats")
    op.execute(_VIEW_WITH_CAMPUS_FILTER)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS school_track_stats")
    op.execute(_VIEW_0001)
