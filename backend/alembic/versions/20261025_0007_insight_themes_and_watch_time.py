"""Persist account themes and supported Reels watch-time metrics."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0007"
down_revision: str | None = "20261024_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instagram_connections") as batch:
        batch.add_column(sa.Column("insight_themes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("insight_themes_updated_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.add_column(sa.Column("average_watch_time_ms", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("total_watch_time_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instagram_insight_snapshots") as batch:
        batch.drop_column("total_watch_time_ms")
        batch.drop_column("average_watch_time_ms")
    with op.batch_alter_table("instagram_connections") as batch:
        batch.drop_column("insight_themes_updated_at")
        batch.drop_column("insight_themes")
