"""Add weekly cadence weekday and one schedule per source."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_schedule_weekday_and_source_unique"
down_revision: str | None = "0002_listing_aggregate_source_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.add_column(sa.Column("weekday", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_crawl_schedules_weekday_range",
            "weekday IS NULL OR weekday BETWEEN 0 AND 6",
        )
        batch_op.create_unique_constraint(
            "uq_crawl_schedules_source_id", ["source_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.drop_constraint("uq_crawl_schedules_source_id", type_="unique")
        batch_op.drop_constraint(
            "ck_crawl_schedules_weekday_range", type_="check"
        )
        batch_op.drop_column("weekday")
