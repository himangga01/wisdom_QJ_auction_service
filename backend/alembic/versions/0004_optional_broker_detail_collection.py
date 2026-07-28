"""Add optional broker detail collection flags."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_optional_broker_detail_collection"
down_revision: str | None = "0003_schedule_weekday_and_source_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("crawl_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "collect_broker_details",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "collect_broker_details",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.drop_column("collect_broker_details")
    with op.batch_alter_table("crawl_runs") as batch_op:
        batch_op.drop_column("collect_broker_details")
