"""tuition_records: them TuitionUnit.DONG_HOC_KY + semesters_per_year_assumed

Owner chot (2026-10-15, sau 2 dot crawl 20 truong): nhieu truong cong bo hoc
phi theo HOC KY (FPT ~31,6tr/ky, DH Ngan hang TP.HCM 12.765.500d/ky, HUST
TROY 30tr/ky) — schema cu khong co don vi nao khop nen crawler phai bo dong
(SKILL.md bay #8). Them enum value + cot `semesters_per_year_assumed` (giong
mau `duration_years_assumed` cua 'dong_toan_khoa', migration 0003) de crawler
quy doi amount_per_year = amount_original * semesters_per_year_assumed.

So hoc ky/nam KHONG luon la 2 (FPT, HUST TROY: 3 ky/nam) nen bat buoc ghi ro,
khong ngam dinh; dong luon needs_review. Xem crawler/schema.py::quy_doi_ve_dong_nam.

ALTER TYPE ... ADD VALUE chay trong autocommit_block rieng — Postgres khong
cho dung gia tri ENUM moi trong cung transaction da them no.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # IF NOT EXISTS: Postgres khong cho DROP VALUE khoi ENUM — idempotent
        # khi chay lai sau mot lan downgrade (xem 0003).
        op.execute("ALTER TYPE tuition_unit ADD VALUE IF NOT EXISTS 'dong_hoc_ky'")

    op.add_column(
        "tuition_records",
        sa.Column("semesters_per_year_assumed", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tuition_semesters_when_hoc_ky",
        "tuition_records",
        "unit_original <> 'dong_hoc_ky' OR semesters_per_year_assumed IS NOT NULL",
    )


def downgrade() -> None:
    # Gia tri ENUM 'dong_hoc_ky' o lai (Postgres khong DROP VALUE) — xem 0003.
    op.drop_constraint("ck_tuition_semesters_when_hoc_ky", "tuition_records")
    op.drop_column("tuition_records", "semesters_per_year_assumed")
