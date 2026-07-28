"""Add Chrome interaction delay presets to runs and schedules."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_interaction_delay_presets"
down_revision: str | None = "0004_optional_broker_detail_collection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRESET_VALUES_SQL = (
    "interaction_delay_preset IN "
    "('very_fast','fast','normal','careful','very_careful')"
)


def upgrade() -> None:
    with op.batch_alter_table("crawl_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "interaction_delay_preset",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'normal'"),
            )
        )
        batch_op.create_check_constraint(
            "ck_crawl_runs_interaction_delay_preset_values",
            PRESET_VALUES_SQL,
        )
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "interaction_delay_preset",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'normal'"),
            )
        )
        batch_op.create_check_constraint(
            "ck_crawl_schedules_interaction_delay_preset_values",
            PRESET_VALUES_SQL,
        )


def downgrade() -> None:
    with op.batch_alter_table("crawl_schedules") as batch_op:
        batch_op.drop_constraint(
            "ck_crawl_schedules_interaction_delay_preset_values",
            type_="check",
        )
        batch_op.drop_column("interaction_delay_preset")
    with op.batch_alter_table("crawl_runs") as batch_op:
        batch_op.drop_constraint(
            "ck_crawl_runs_interaction_delay_preset_values",
            type_="check",
        )
        batch_op.drop_column("interaction_delay_preset")
