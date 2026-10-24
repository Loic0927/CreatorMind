"""Add reusable account context for generation and analysis."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261024_0005"
down_revision: str | None = "20261022_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_context", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("users", "account_context")
