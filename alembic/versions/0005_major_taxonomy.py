"""major taxonomy: taxonomy_nodes + major_aliases + FK majors.code (buoc "mo rong")

Thay 6 nhom nganh tu dat bang cay phan loai chinh thuc cua Bo GD&DT (Thong tu
09/2022/TT-BGDDT): Linh vuc (3 so) -> Nhom nganh (5 so) -> Nganh (7 so). Xem
docs/plans/2026-09-29-001-feat-major-taxonomy-ontology-plan.md.

CHI THEM, khong bo gi: `major_groups` va `majors.group_code` van con nguyen —
image cu va FE cu van chay duoc tren schema moi (buoc "thu hep" la migration
0006, sau khi FE moi da live). Nho vay `release_command = alembic upgrade head`
(fly.toml) an toan chay TRUOC khi doi traffic.

- `taxonomy_nodes`: 1 bang tu tham chieu (adjacency list) cho ca 3 cap. Cac CHECK
  dua luat du lieu xuong DB: do dai ma theo cap, cap 1 khong co cha, ma con bat
  dau bang ma cha — de file seed sai bi tu choi ngay luc nap.
- `majors.code` (cot da co, tung nullable/khong unique, hien NULL het) thanh FK toi
  `taxonomy_nodes.code`. NULL = "Chua phan loai". Rang buoc "phai tro toi nut cap
  3" khong CHECK xuyen bang duoc -> test (tests/test_taxonomy_seed.py) giu.
- `major_aliases`: ten goi khac de tim kiem, gan vao `majors` cua hocphi (khong
  gan vao nut danh muc) de nganh "Chua phan loai" van co alias.

Du lieu nap bang `scripts/seed.py` (seeds/004..006), khong nap trong migration.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_nodes",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("parent_code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["parent_code"], ["taxonomy_nodes.code"]),
        sa.CheckConstraint("level IN (1, 2, 3)", name="ck_taxonomy_nodes_level"),
        sa.CheckConstraint(
            "(level = 1) = (parent_code IS NULL)", name="ck_taxonomy_nodes_root"
        ),
        sa.CheckConstraint(
            "char_length(code) = CASE level WHEN 1 THEN 3 WHEN 2 THEN 5 ELSE 7 END",
            name="ck_taxonomy_nodes_code_length",
        ),
        sa.CheckConstraint(
            "parent_code IS NULL OR code LIKE parent_code || '%'",
            name="ck_taxonomy_nodes_code_prefix",
        ),
    )
    op.create_index("ix_taxonomy_nodes_parent_code", "taxonomy_nodes", ["parent_code"])

    op.create_foreign_key(
        "fk_majors_code_taxonomy_nodes",
        "majors",
        "taxonomy_nodes",
        ["code"],
        ["code"],
    )

    op.create_table(
        "major_aliases",
        sa.Column("major_id", sa.Text(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        # bo dau + lowercase (app/text.py::normalize), tinh luc nap seed.
        sa.Column("alias_normalized", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("major_id", "alias_normalized"),
        sa.ForeignKeyConstraint(["major_id"], ["majors.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_major_aliases_alias_normalized", "major_aliases", ["alias_normalized"]
    )


def downgrade() -> None:
    op.drop_table("major_aliases")
    op.drop_constraint("fk_majors_code_taxonomy_nodes", "majors", type_="foreignkey")
    op.drop_table("taxonomy_nodes")
