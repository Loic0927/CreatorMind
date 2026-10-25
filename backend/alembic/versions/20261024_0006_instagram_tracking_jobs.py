"""Add durable Instagram post-publish milestone collection jobs."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261024_0006"
down_revision: str | None = "20261024_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.alter_column(
            "engagement_rate",
            existing_type=sa.Float(),
            nullable=True,
        )
        batch.add_column(sa.Column("metric_status", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("collection_type", sa.String(length=32), nullable=False, server_default="manual_current"))
        batch.add_column(sa.Column("target_hour", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint(
            "uq_instagram_snapshot_milestone",
            ["media_id", "target_hour"],
        )
    op.create_table(
        "instagram_insight_collection_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.String(length=255), nullable=False),
        sa.Column("target_hour", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_hour IN (1, 3, 6, 12, 24)", name="ck_instagram_insight_job_target_hour"),
        sa.ForeignKeyConstraint(["media_id"], ["instagram_media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["instagram_insight_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
        sa.UniqueConstraint("tracked_post_id", "target_hour", name="uq_instagram_insight_job_milestone"),
    )
    op.create_index("ix_instagram_insight_collection_jobs_user_id", "instagram_insight_collection_jobs", ["user_id"])
    op.create_index("ix_instagram_insight_collection_jobs_tracked_post_id", "instagram_insight_collection_jobs", ["tracked_post_id"])
    op.create_index("ix_instagram_insight_collection_jobs_media_id", "instagram_insight_collection_jobs", ["media_id"])
    op.create_index("ix_instagram_insight_collection_jobs_next_attempt_at", "instagram_insight_collection_jobs", ["next_attempt_at"])
    op.create_index("ix_instagram_insight_collection_jobs_status", "instagram_insight_collection_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("instagram_insight_collection_jobs")
    op.execute("UPDATE instagram_insight_snapshots SET engagement_rate = 0 WHERE engagement_rate IS NULL")
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.drop_constraint("uq_instagram_snapshot_milestone", type_="unique")
        batch.drop_column("scheduled_for")
        batch.drop_column("target_hour")
        batch.drop_column("collection_type")
        batch.drop_column("metric_status")
        batch.alter_column(
            "engagement_rate",
            existing_type=sa.Float(),
            nullable=False,
        )
