"""Add durable tracking dead letters and overdue-alert state.

Revision ID: 20261125_0019
Revises: 20261125_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261125_0019"
down_revision: str | None = "20261125_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.add_column(sa.Column("overdue_alerted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "instagram_tracking_dead_letters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tracked_post_id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.String(length=255), nullable=False),
        sa.Column("milestone_hours", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=128), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tracked_post_id"], ["tracked_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["instagram_media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracked_post_id", name="uq_instagram_tracking_dead_letter_post"),
    )
    op.create_index(
        "ix_instagram_tracking_dead_letters_user_id",
        "instagram_tracking_dead_letters",
        ["user_id"],
    )
    op.create_index(
        "ix_instagram_tracking_dead_letters_tracked_post_id",
        "instagram_tracking_dead_letters",
        ["tracked_post_id"],
    )
    op.create_index(
        "ix_instagram_tracking_dead_letters_media_id",
        "instagram_tracking_dead_letters",
        ["media_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_instagram_tracking_dead_letters_media_id",
        table_name="instagram_tracking_dead_letters",
    )
    op.drop_index(
        "ix_instagram_tracking_dead_letters_tracked_post_id",
        table_name="instagram_tracking_dead_letters",
    )
    op.drop_index(
        "ix_instagram_tracking_dead_letters_user_id",
        table_name="instagram_tracking_dead_letters",
    )
    op.drop_table("instagram_tracking_dead_letters")
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.drop_column("overdue_alerted_at")
