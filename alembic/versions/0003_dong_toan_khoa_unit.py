"""tuition_records: them TuitionUnit.DONG_TOAN_KHOA + duration_years_assumed

Owner chot (2026-09-05, sau khi crawl HUTECH): mot so truong tu thuc cong bo
hoc phi theo kieu "tron goi toan khoa, on dinh" (vd HUTECH khoa 2026: X trieu
dong / N nam, khong tang) thay vi dong/nam hay dong/tin chi. Schema cu khong
co don vi nao khop — them enum value + cot `duration_years_assumed` (giong
mau `credits_per_year_assumed` cua 'dong_tin_chi') de crawler quy doi
amount_per_year = amount_original / duration_years_assumed, luon danh dau
needs_review vi day la suy ra (gia dinh chia deu theo nam), khong phai muc
tung nam truong cong bo rieng. Xem crawler/schema.py::quy_doi_ve_dong_nam.

ALTER TYPE ... ADD VALUE chay trong autocommit_block rieng — Postgres khong
cho dung gia tri ENUM moi trong cung transaction da them no.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # IF NOT EXISTS: Postgres khong cho DROP VALUE khoi ENUM (xem downgrade
        # ben duoi) — idempotent phong khi migration nay bi chay lai tren mot
        # DB da tung upgrade len 0003 roi downgrade (gia tri enum van con lai).
        op.execute("ALTER TYPE tuition_unit ADD VALUE IF NOT EXISTS 'dong_toan_khoa'")

    op.add_column(
        "tuition_records",
        # Numeric, khong phai smallint — ho tro khoa 3,5/4,5 nam (7/9 hoc ky).
        sa.Column("duration_years_assumed", sa.Numeric(3, 1), nullable=True),
    )
    op.create_check_constraint(
        "ck_tuition_duration_when_toan_khoa",
        "tuition_records",
        "unit_original <> 'dong_toan_khoa' OR duration_years_assumed IS NOT NULL",
    )


def downgrade() -> None:
    # Khong the DROP VALUE khoi ENUM Postgres — neu downgrade tiep xuong 0001
    # thi ca type `tuition_unit` bi DROP TYPE luon nen khong can xu ly rieng
    # o day (xem 0001_initial_schema.py::downgrade).
    op.drop_constraint("ck_tuition_duration_when_toan_khoa", "tuition_records")
    op.drop_column("tuition_records", "duration_years_assumed")
