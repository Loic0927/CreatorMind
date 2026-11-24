"""Add official TikTok public post metrics."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0017"
down_revision = "20261124_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tiktok_tracked_posts", sa.Column("likes", sa.Integer(), nullable=True))
    op.add_column("tiktok_tracked_posts", sa.Column("comments", sa.Integer(), nullable=True))
    op.add_column("tiktok_tracked_posts", sa.Column("shares", sa.Integer(), nullable=True))
    op.add_column("tiktok_tracked_posts", sa.Column("views", sa.Integer(), nullable=True))
    op.add_column("tiktok_tracked_posts", sa.Column("engagement_rate", sa.Float(), nullable=True))
    op.add_column("tiktok_tracked_posts", sa.Column("metrics_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tiktok_tracked_posts", "metrics_updated_at")
    op.drop_column("tiktok_tracked_posts", "engagement_rate")
    op.drop_column("tiktok_tracked_posts", "views")
    op.drop_column("tiktok_tracked_posts", "shares")
    op.drop_column("tiktok_tracked_posts", "comments")
    op.drop_column("tiktok_tracked_posts", "likes")
