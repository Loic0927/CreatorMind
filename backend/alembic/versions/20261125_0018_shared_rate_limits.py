"""Add shared database-backed rate-limit storage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261125_0018"
down_revision: str | None = "20261124_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(length=512), nullable=False),
        sa.Column("hits", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("rate_limits")
