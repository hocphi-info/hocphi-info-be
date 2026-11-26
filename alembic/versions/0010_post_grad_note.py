"""post_grad_requirements: them cot `note` (ghi chu tung buoc hanh nghe)

F10 (2026-11-26): bat that chi phi hanh nghe sau tot nghiep, bat dau tu Luat su.
Moi buoc can 1 dong ghi chu ngan hien nguyen van tren FE: cach uoc luong khi phi
chua ban hanh (vd ky thi quoc gia ve luat su theo Luat Luat su sua doi 2026), hoac
khoan dinh ky KHONG cong vao tong (vd doan phi ~250.000d/thang). Khong them cot
"included_in_total": khoan dinh ky khong la 1 buoc, chi la ghi chu cua buoc lien quan.

Ngay kiem tra nguon dung `sources.checked_at` co san (0001) — khong them cot.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("post_grad_requirements", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("post_grad_requirements", "note")
