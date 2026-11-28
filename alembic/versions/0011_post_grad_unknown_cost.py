"""post_grad_requirements: cho phep chi phi "chua cong bo" (cost_min/cost_max NULL)

F10, nghe bac si (2026-11-28): phi ky kiem tra danh gia nang luc hanh nghe (Hoi
dong Y khoa Quoc gia, bat buoc tu 01/01/2027) CHUA cong bo — Hoi dong xay dung,
Bo Y te duyet. Ghi 0 se thanh "mien phi" (sai); khong co co so de uoc luong. NULL
ca 2 cot = chua cong bo: FE hien "Chua cong bo", tong chi cong cac buoc da biet
va ghi ro "chua gom khoan chua cong bo".

CHECK moi: 2 cot cung NULL hoac cung co gia tri. `ck_postgrad_cost_range`
(cost_max >= cost_min) giu nguyen — voi NULL thi Postgres coi la dat.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "post_grad_requirements",
        "cost_min",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "post_grad_requirements",
        "cost_max",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_postgrad_cost_known",
        "post_grad_requirements",
        "(cost_min IS NULL) = (cost_max IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_postgrad_cost_known", "post_grad_requirements")
    # Buoc chua cong bo khong co cach bieu dien o schema cu -> ve 0 (chi khi ha cap).
    op.execute(
        "UPDATE post_grad_requirements SET cost_min = 0, cost_max = 0 "
        "WHERE cost_min IS NULL"
    )
    op.alter_column(
        "post_grad_requirements",
        "cost_min",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "post_grad_requirements",
        "cost_max",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
