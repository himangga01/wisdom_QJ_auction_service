"""Persist the Task 6 aggregate source count."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_listing_aggregate_source_count"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("listing_aggregates") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_count", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.alter_column("source_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("listing_aggregates") as batch_op:
        batch_op.drop_column("source_count")
