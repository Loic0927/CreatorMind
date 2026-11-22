"""Persist Meta data-deletion confirmation statuses.

Revision ID: 20261102_0013
Revises: 20261101_0012
"""

import sqlalchemy as sa
from alembic import op

revision = "20261102_0013"
down_revision = "20261101_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_data_deletion_requests",
        sa.Column("code", sa.String(length=128), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_instagram_data_deletion_requests_created_at",
        "instagram_data_deletion_requests",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("instagram_data_deletion_requests")
