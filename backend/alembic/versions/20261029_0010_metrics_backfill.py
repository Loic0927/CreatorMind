"""Allow idempotent lifetime metrics backfill jobs.

Revision ID: 20261029_0010
Revises: 20261029_0009
"""
from alembic import op

revision = "20261029_0010"
down_revision = "20261029_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.drop_constraint("ck_instagram_insight_job_target_hour", type_="check")
        batch.create_check_constraint("ck_instagram_insight_job_target_hour", "target_hour IN (-1, 24)")


def downgrade() -> None:
    op.execute("DELETE FROM instagram_insight_collection_jobs WHERE target_hour = -1")
    with op.batch_alter_table("instagram_insight_collection_jobs") as batch:
        batch.drop_constraint("ck_instagram_insight_job_target_hour", type_="check")
        batch.create_check_constraint("ck_instagram_insight_job_target_hour", "target_hour = 24")
