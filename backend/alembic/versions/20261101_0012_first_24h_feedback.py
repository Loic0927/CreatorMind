"""Restore first-24h collection and evidence-traceable feedback.

Revision ID: 20261101_0012
Revises: 20261030_0011
"""

from alembic import op
import sqlalchemy as sa

revision = "20261101_0012"
down_revision = "20261030_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("instagram_connections") as batch:
        batch.add_column(sa.Column("tracking_start_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    with op.batch_alter_table("tracked_posts") as batch:
        batch.add_column(sa.Column("first_24h_status", sa.String(32), nullable=False, server_default="collecting"))
        batch.add_column(sa.Column("first_24h_reason", sa.String(128), nullable=True))
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("milestone_hours", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source", sa.String(32), nullable=False, server_default="api"))
        batch.add_column(sa.Column("lateness_seconds", sa.Integer(), nullable=True))
        batch.create_unique_constraint("uq_instagram_snapshot_milestone", ["media_id", "milestone_hours"])
    with op.batch_alter_table("insight_text_cache") as batch:
        batch.add_column(sa.Column("provider", sa.String(32), nullable=False, server_default="template"))
        batch.add_column(sa.Column("prompt_version", sa.String(64), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("facts_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

    op.create_table(
        "instagram_insight_collection_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("tracked_post_id", sa.String(36), nullable=False),
        sa.Column("media_id", sa.String(255), nullable=False),
        sa.Column("milestone_hours", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=True, unique=True),
        sa.Column("reason", sa.String(128), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("milestone_hours IN (1, 3, 6, 12, 24)", name="ck_instagram_insight_job_milestone"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["instagram_media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["instagram_insight_snapshots.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tracked_post_id", "milestone_hours", name="uq_instagram_insight_job_milestone"),
    )
    for column in ("user_id", "tracked_post_id", "media_id", "next_attempt_at", "status"):
        op.create_index(f"ix_instagram_insight_collection_jobs_{column}", "instagram_insight_collection_jobs", [column])

    op.create_table(
        "ai_generation_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generator", sa.String(64), nullable=False),
        sa.Column("tracked_post_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_generation_log_tracked_post_id", "ai_generation_log", ["tracked_post_id"])
    op.create_index("ix_ai_generation_log_status", "ai_generation_log", ["status"])
    op.create_index("ix_ai_generation_log_created_at", "ai_generation_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_generation_log")
    op.drop_table("instagram_insight_collection_jobs")
    with op.batch_alter_table("insight_text_cache") as batch:
        batch.drop_column("facts_json")
        batch.drop_column("prompt_version")
        batch.drop_column("provider")
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.drop_constraint("uq_instagram_snapshot_milestone", type_="unique")
        batch.drop_column("lateness_seconds")
        batch.drop_column("source")
        batch.drop_column("milestone_hours")
        batch.drop_column("scheduled_for")
    with op.batch_alter_table("tracked_posts") as batch:
        batch.drop_column("first_24h_reason")
        batch.drop_column("first_24h_status")
    with op.batch_alter_table("instagram_connections") as batch:
        batch.drop_column("tracking_start_at")
