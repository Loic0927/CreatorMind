"""Remove retired derived insights and add small AI text caches.

Revision ID: 20261030_0011
Revises: 20261029_0010
"""

from alembic import op
import sqlalchemy as sa


revision = "20261030_0011"
down_revision = "20261029_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep every metric snapshot row. Only milestone/capture metadata is retired.
    op.drop_table("instagram_insight_collection_jobs")
    op.drop_table("external_insight_records")
    op.drop_table("tracked_post_analyses")

    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.drop_constraint("uq_instagram_snapshot_milestone", type_="unique")
        batch.drop_column("scheduled_for")
        batch.drop_column("target_hour")
        batch.drop_column("collection_type")

    with op.batch_alter_table("instagram_connections") as batch:
        batch.drop_column("insight_themes_updated_at")
        batch.drop_column("insight_themes")
        batch.drop_column("audience_activity_updated_at")
        batch.drop_column("audience_activity_insight")
        batch.drop_column("auto_track_new_posts")
        batch.drop_column("timezone_offset_minutes")
        batch.add_column(sa.Column("session_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("session_sync_error", sa.String(length=128), nullable=True))

    with op.batch_alter_table("tracked_posts") as batch:
        batch.drop_column("exclude_from_comparisons")

    with op.batch_alter_table("instagram_comments") as batch:
        batch.drop_column("classification_model")
        batch.drop_column("category")

    op.create_table(
        "insight_text_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=True),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cache_key", name="uq_insight_text_cache_user_key"),
    )
    op.create_index("ix_insight_text_cache_user_id", "insight_text_cache", ["user_id"])
    op.create_index("ix_insight_text_cache_tracked_post_id", "insight_text_cache", ["tracked_post_id"])


def downgrade() -> None:
    op.drop_table("insight_text_cache")

    with op.batch_alter_table("instagram_comments") as batch:
        batch.add_column(sa.Column("category", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("classification_model", sa.String(length=128), nullable=True))

    with op.batch_alter_table("tracked_posts") as batch:
        batch.add_column(sa.Column("exclude_from_comparisons", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("instagram_connections") as batch:
        batch.drop_column("session_sync_error")
        batch.drop_column("session_synced_at")
        batch.add_column(sa.Column("timezone_offset_minutes", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("auto_track_new_posts", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("audience_activity_insight", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("audience_activity_updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("insight_themes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("insight_themes_updated_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.add_column(sa.Column("collection_type", sa.String(length=32), nullable=False, server_default="manual_current"))
        batch.add_column(sa.Column("target_hour", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_instagram_snapshot_milestone", ["media_id", "target_hour"])

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

    op.create_table(
        "external_insight_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("extraction_model", sa.String(length=128), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("screenshot_objects", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_insight_records_user_id", "external_insight_records", ["user_id"])
    op.create_index("ix_external_insight_records_tracked_post_id", "external_insight_records", ["tracked_post_id"])
    op.create_index("ix_external_insight_records_created_at", "external_insight_records", ["created_at"])

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
        sa.CheckConstraint("target_hour IN (-1, 24)", name="ck_instagram_insight_job_target_hour"),
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
