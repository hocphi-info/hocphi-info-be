"""comments + comment_reports: binh luan an danh, long nhau

Owner yeu cau (2026-11-11): ai cung binh luan duoc (khong dang nhap) o /nganh,
/truong, /truong/{slug}, /nganh/{truong}/{nganh}, /bai-viet[/{slug}], tra loi
long nhau khong gioi han do sau du lieu (UI tu lam phang tu cap 4).

Duong GHI cong khai dau tien cua API. Khong luu IP tho: `ip_hash` = HMAC(IP) dung
cho gioi han toc do + chong bao cao trung; `author_tag` = HMAC(IP + chuoi)[:4]
de phan biet "An danh" nay voi "An danh" kia trong 1 chuoi.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REASON = postgresql.ENUM(
    "spam",
    "sai_lech",
    "xuc_pham",
    "thong_tin_ca_nhan",
    "khac",
    name="comment_report_reason",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE comment_report_reason AS ENUM "
        "('spam', 'sai_lech', 'xuc_pham', 'thong_tin_ca_nhan', 'khac')"
    )
    op.create_table(
        "comments",
        sa.Column(
            "id", sa.Text(), primary_key=True, server_default=sa.text("gen_ulid()")
        ),
        sa.Column("thread_key", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("root_id", sa.Text(), sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("author_tag", sa.String(8), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.Text(), nullable=False),
        sa.Column("delete_token_hash", sa.Text(), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 3 AND 2000", name="ck_comments_body_len"
        ),
        sa.CheckConstraint(
            "author_name IS NULL OR char_length(author_name) BETWEEN 1 AND 40",
            name="ck_comments_author_name_len",
        ),
        sa.CheckConstraint("depth >= 0", name="ck_comments_depth"),
        sa.CheckConstraint(
            "(parent_id IS NULL) = (root_id IS NULL)",
            name="ck_comments_root_matches_parent",
        ),
    )
    op.create_index(
        "ix_comments_thread_roots",
        "comments",
        ["thread_key", "created_at"],
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index("ix_comments_root_id", "comments", ["root_id"])
    op.create_index(
        "ix_comments_ip_hash_created_at", "comments", ["ip_hash", "created_at"]
    )

    op.create_table(
        "comment_reports",
        sa.Column(
            "id", sa.Text(), primary_key=True, server_default=sa.text("gen_ulid()")
        ),
        sa.Column(
            "comment_id",
            sa.Text(),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip_hash", sa.Text(), nullable=False),
        sa.Column("reason", _REASON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_comment_reports_ip",
        "comment_reports",
        ["comment_id", "ip_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("comment_reports")
    op.drop_table("comments")
    op.execute("DROP TYPE comment_report_reason")
