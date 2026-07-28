"""Promote canonical apartment basic details."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_apartment_basic_details"
down_revision: str | None = "0005_interaction_delay_presets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("apartments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "details_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column("details_updated_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("apartments") as batch_op:
        batch_op.drop_column("details_updated_at")
        batch_op.drop_column("details_json")
