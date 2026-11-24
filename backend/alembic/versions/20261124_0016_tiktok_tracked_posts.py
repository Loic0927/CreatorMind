"""Add selected TikTok posts."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0016"
down_revision = "20261123_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tiktok_tracked_posts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("video_id", sa.String(length=255), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_tiktok_tracked_posts_user_video"),
    )
    op.create_index("ix_tiktok_tracked_posts_user_id", "tiktok_tracked_posts", ["user_id"])
    op.create_index("ix_tiktok_tracked_posts_published_at", "tiktok_tracked_posts", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_tiktok_tracked_posts_published_at", table_name="tiktok_tracked_posts")
    op.drop_index("ix_tiktok_tracked_posts_user_id", table_name="tiktok_tracked_posts")
    op.drop_table("tiktok_tracked_posts")
