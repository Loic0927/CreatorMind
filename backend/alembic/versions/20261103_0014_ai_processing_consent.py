"""Store explicit user consent for Gemini AI processing.

Revision ID: 20261103_0014
Revises: 20261102_0013
"""

import sqlalchemy as sa
from alembic import op

revision = "20261103_0014"
down_revision = "20261102_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable keeps existing users readable and requires a fresh opt-in.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("ai_processing_consented_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("ai_processing_consented_at")
