"""Add TikTok OAuth state and connection storage."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_0015"
down_revision = "20261103_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tiktok_oauth_states",
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("client", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_tiktok_oauth_states_user_id", "tiktok_oauth_states", ["user_id"])
    op.create_table(
        "tiktok_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("open_id", sa.String(length=255), nullable=False),
        sa.Column("union_id", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("open_id", name="uq_tiktok_connections_open_id"),
        sa.UniqueConstraint("user_id", name="uq_tiktok_connections_user_id"),
    )
    op.create_index("ix_tiktok_connections_user_id", "tiktok_connections", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tiktok_connections_user_id", table_name="tiktok_connections")
    op.drop_table("tiktok_connections")
    op.drop_index("ix_tiktok_oauth_states_user_id", table_name="tiktok_oauth_states")
    op.drop_table("tiktok_oauth_states")
