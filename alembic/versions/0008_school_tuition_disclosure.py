"""schools: them danh gia muc cong khai hoc phi (tuition_disclosure)

Owner chot (2026-10-16, sau khi verify DH Hoa Sen): mot so truong khong cong bo
hoc phi theo nganh — Hoa Sen chi ghi "45-85 trieu/nam tuy chuong trinh", hoc
phi that chi xem duoc trong App Hoa Sen sau khi nhap hoc. Day la thong tin
huu ich cho phu huynh nen luu thanh du lieu, khong de trong.

Chi 2 muc (TuitionDisclosure): 'theo_nganh' (xanh) / 'khong_minh_bach' (do).
NULL = chua danh gia. Danh gia la nhan dinh cua nguoi van hanh nen bat buoc
kem ngay kiem tra + link bang chung (CHECK) — de bao ve khi bi phan bac.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DISCLOSURE = postgresql.ENUM(
    "theo_nganh", "khong_minh_bach", name="tuition_disclosure", create_type=False
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE tuition_disclosure AS ENUM ('theo_nganh', 'khong_minh_bach')"
    )
    op.add_column("schools", sa.Column("tuition_disclosure", _DISCLOSURE))
    op.add_column(
        "schools", sa.Column("tuition_disclosure_checked_on", sa.Date(), nullable=True)
    )
    op.add_column(
        "schools",
        sa.Column("tuition_disclosure_evidence_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "schools", sa.Column("tuition_disclosure_note", sa.Text(), nullable=True)
    )
    op.create_check_constraint(
        "ck_schools_disclosure_evidence",
        "schools",
        "tuition_disclosure IS NULL OR "
        "(tuition_disclosure_checked_on IS NOT NULL "
        "AND tuition_disclosure_evidence_url IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_schools_disclosure_evidence", "schools")
    op.drop_column("schools", "tuition_disclosure_note")
    op.drop_column("schools", "tuition_disclosure_evidence_url")
    op.drop_column("schools", "tuition_disclosure_checked_on")
    op.drop_column("schools", "tuition_disclosure")
    op.execute("DROP TYPE tuition_disclosure")
