"""Add comments, screenshot insights, exclusions, and keep only the 24-hour job."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_0008"
down_revision: str | None = "20261025_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM instagram_insight_collection_jobs WHERE target_hour <> 24")
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.drop_constraint("ck_instagram_insight_job_target_hour", type_="check")
        batch.create_check_constraint("ck_instagram_insight_job_target_hour", "target_hour = 24")
    with op.batch_alter_table("tracked_posts") as batch:
        batch.add_column(sa.Column("exclude_from_comparisons", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "instagram_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_owner_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("classification_model", sa.String(length=128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider_id", name="uq_instagram_comments_user_provider"),
    )
    op.create_index("ix_instagram_comments_user_id", "instagram_comments", ["user_id"])
    op.create_index("ix_instagram_comments_tracked_post_id", "instagram_comments", ["tracked_post_id"])

    op.create_table(
        "external_insight_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("extraction_model", sa.String(length=128), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("screenshot_objects", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_insight_records_user_id", "external_insight_records", ["user_id"])
    op.create_index("ix_external_insight_records_tracked_post_id", "external_insight_records", ["tracked_post_id"])
    op.create_index("ix_external_insight_records_created_at", "external_insight_records", ["created_at"])


def downgrade() -> None:
    op.drop_table("external_insight_records")
    op.drop_table("instagram_comments")
    with op.batch_alter_table("tracked_posts") as batch:
        batch.drop_column("exclude_from_comparisons")
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.drop_constraint("ck_instagram_insight_job_target_hour", type_="check")
        batch.create_check_constraint(
            "ck_instagram_insight_job_target_hour",
            "target_hour IN (1, 3, 6, 12, 24)",
        )
