"""Account tracking preferences.

Revision ID: 20261029_0009
Revises: 20261028_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_0009"
down_revision = "20261028_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instagram_connections", sa.Column("auto_track_new_posts", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("instagram_connections", sa.Column("timezone_offset_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("instagram_connections", sa.Column("audience_activity_insight", sa.JSON(), nullable=True))
    op.add_column("instagram_connections", sa.Column("audience_activity_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("instagram_connections", "audience_activity_updated_at")
    op.drop_column("instagram_connections", "audience_activity_insight")
    op.drop_column("instagram_connections", "timezone_offset_minutes")
    op.drop_column("instagram_connections", "auto_track_new_posts")
