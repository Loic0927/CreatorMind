"""Persist content-aware analyses for tracked posts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_0003"
down_revision: str | None = "20261017_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracked_post_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_ids", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("observed_metrics", sa.JSON(), nullable=False),
        sa.Column("metric_deltas", sa.JSON(), nullable=False),
        sa.Column("content_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["instagram_insight_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracked_post_analyses_user_id", "tracked_post_analyses", ["user_id"])
    op.create_index("ix_tracked_post_analyses_tracked_post_id", "tracked_post_analyses", ["tracked_post_id"])
    op.create_index("ix_tracked_post_analyses_source_snapshot_id", "tracked_post_analyses", ["source_snapshot_id"])
    op.create_index("ix_tracked_post_analyses_created_at", "tracked_post_analyses", ["created_at"])


def downgrade() -> None:
    op.drop_table("tracked_post_analyses")
