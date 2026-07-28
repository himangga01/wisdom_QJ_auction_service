"""Add source notification preferences and in-app notifications."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_in_app_notifications"
down_revision: str | None = "0008_source_owner_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_notification_preferences",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notify_new", sa.Boolean(), nullable=False),
        sa.Column("notify_changed", sa.Boolean(), nullable=False),
        sa.Column("notify_removed", sa.Boolean(), nullable=False),
        sa.Column("notify_restored", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["tracked_sources.id"],
            name="fk_source_notification_preferences_source_id_tracked_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "source_id", name="pk_source_notification_preferences"
        ),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=False),
        sa.Column("apartment_id", sa.Uuid(), nullable=False),
        sa.Column("listing_group_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("compare_run_id", sa.Uuid(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('new','changed','removed','restored')",
            name="ck_notifications_event_type_values",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_notifications_user_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tracked_sources.id"],
            name="fk_notifications_source_id_tracked_sources", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["crawl_runs.id"],
            name="fk_notifications_run_id_crawl_runs", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["compare_run_id"], ["crawl_runs.id"],
            name="fk_notifications_compare_run_id_crawl_runs", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["change_event_id"], ["change_events.id"],
            name="fk_notifications_change_event_id_change_events", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["apartment_id"], ["apartments.id"],
            name="fk_notifications_apartment_id_apartments", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["listing_group_id"], ["listing_groups.id"],
            name="fk_notifications_listing_group_id_listing_groups", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.UniqueConstraint(
            "user_id", "change_event_id",
            name="uq_notifications_user_change_event"
        ),
    )
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "read_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_source_created",
        "notifications",
        ["source_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_source_created", table_name="notifications"
    )
    op.drop_index(
        "ix_notifications_user_read_created", table_name="notifications"
    )
    op.drop_table("notifications")
    op.drop_table("source_notification_preferences")
