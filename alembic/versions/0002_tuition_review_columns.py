"""tuition_records: them needs_review + review_reason

Owner chot (plan Tuan 2, 2026-09-05): giu trang thai "chua duyet het" cua
AI-crawler qua tang DB thay vi chi nam trong seeds/*.jsonl. Hai cot nullable/
co default — khong dung ai het du lieu cu, khong can backfill.

`needs_review` khong lo ra API o Tuan 2 (chua co UI hien "dong chua chac") —
chi de tra soat truc tiep trong DB khi can.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tuition_records",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "tuition_records",
        sa.Column("review_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tuition_records", "review_reason")
    op.drop_column("tuition_records", "needs_review")
