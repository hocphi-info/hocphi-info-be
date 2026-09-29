"""drop major_groups + majors.group_code (buoc "thu hep" cua chang A)

Sau khi FE moi (loc theo Linh vuc, doc `taxonomy`) da live va seed taxonomy da
chay tren prod, 6 nhom nganh tu dat khong con ai doc -> bo hang de chi con MOT he
phan loai (taxonomy_nodes, migration 0005). Xem
docs/plans/2026-09-29-001-feat-major-taxonomy-ontology-plan.md (U10).

downgrade() dung lai bang + cot de round-trip `downgrade base` chay duoc, nhung
KHONG khoi phuc gia tri nhom cua tung nganh (cot tra ve nullable, NULL het) — du
lieu 6 nhom da bi xoa, tai tao duoc chi bang cach gan lai tay.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GROUPS = [
    ("CNTT", "Cong nghe thong tin"),
    ("KY_THUAT", "Ky thuat"),
    ("KINH_TE", "Kinh te - Tai chinh - Quan tri"),
    ("Y_DUOC", "Y - Duoc"),
    ("LUAT", "Luat"),
    ("LOGISTICS", "Logistics & Quan ly chuoi cung ung"),
]


def upgrade() -> None:
    # Cot bi drop keo theo FK `majors_group_code_fkey` (Postgres tu bo).
    op.drop_column("majors", "group_code")
    op.drop_table("major_groups")


def downgrade() -> None:
    groups = op.create_table(
        "major_groups",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.bulk_insert(groups, [{"code": c, "name": n} for c, n in _GROUPS])
    op.add_column(
        "majors",
        sa.Column("group_code", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "majors_group_code_fkey", "majors", "major_groups", ["group_code"], ["code"]
    )
