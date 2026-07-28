"""Initial persistent analysis schema."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, nullable=False)


def utc_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "tracked_sources",
        uuid_pk(),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("naver_complex_id", sa.String(64)),
        utc_column("created_at"),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("url_hash", name="uq_tracked_sources_url_hash"),
    )
    op.create_table(
        "apartments",
        uuid_pk(),
        sa.Column("naver_complex_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        utc_column("created_at"),
        utc_column("updated_at"),
        sa.UniqueConstraint("naver_complex_id", name="uq_apartments_naver_complex_id"),
    )
    op.create_table(
        "crawl_runs",
        uuid_pk(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        utc_column("created_at"),
        utc_column("started_at", nullable=True),
        utc_column("finished_at", nullable=True),
        sa.Column("error_code", sa.String(80)),
        sa.Column("selector_version", sa.String(80)),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_crawl_runs_progress_range"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','partial','failed','blocked','cancelled')",
            name="ck_crawl_runs_status_values",
        ),
        sa.CheckConstraint(
            "stage IN ('url','complex','listings','brokers','details','compare','save')",
            name="ck_crawl_runs_stage_values",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tracked_sources.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_crawl_runs_source_id", "crawl_runs", ["source_id"])
    op.create_index(
        "uq_crawl_runs_active_source",
        "crawl_runs",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "listing_groups",
        uuid_pk(),
        sa.Column("apartment_id", sa.Uuid(), nullable=False),
        sa.Column("identity_key", sa.String(128), nullable=False),
        utc_column("first_seen_at"),
        utc_column("last_seen_at"),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "apartment_id", "identity_key", name="uq_listing_groups_apartment_id"
        ),
    )
    op.create_index("ix_listing_groups_apartment_id", "listing_groups", ["apartment_id"])
    op.create_table(
        "apartment_snapshots",
        uuid_pk(),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("apartment_id", sa.Uuid(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        utc_column("captured_at"),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "run_id", "apartment_id", name="uq_apartment_snapshots_run_id"
        ),
    )
    op.create_index("ix_apartment_snapshots_run_id", "apartment_snapshots", ["run_id"])
    op.create_index(
        "ix_apartment_snapshots_apartment_id", "apartment_snapshots", ["apartment_id"]
    )
    op.create_table(
        "listing_snapshots",
        uuid_pk(),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("listing_group_id", sa.Uuid(), nullable=False),
        sa.Column("trade_type", sa.String(30), nullable=False),
        sa.Column("price", sa.BigInteger()),
        sa.Column("deposit", sa.BigInteger()),
        sa.Column("monthly_rent", sa.BigInteger()),
        sa.Column("building", sa.String(80)),
        sa.Column("floor", sa.String(80)),
        sa.Column("direction", sa.String(80)),
        sa.Column("supply_area", sa.Numeric(10, 2)),
        sa.Column("exclusive_area", sa.Numeric(10, 2)),
        sa.Column("status", sa.String(20), nullable=False),
        utc_column("captured_at"),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["listing_group_id"], ["listing_groups.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "run_id", "listing_group_id", name="uq_listing_snapshots_run_id"
        ),
    )
    op.create_index("ix_listing_snapshots_run_id", "listing_snapshots", ["run_id"])
    op.create_index(
        "ix_listing_snapshots_listing_group_id",
        "listing_snapshots",
        ["listing_group_id"],
    )
    op.create_table(
        "broker_articles",
        uuid_pk(),
        sa.Column("listing_group_id", sa.Uuid(), nullable=False),
        sa.Column("naver_article_id", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("is_npay", sa.Boolean(), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=False),
        utc_column("first_seen_at"),
        utc_column("last_seen_at"),
        sa.ForeignKeyConstraint(
            ["listing_group_id"], ["listing_groups.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "naver_article_id", name="uq_broker_articles_naver_article_id"
        ),
    )
    op.create_index(
        "ix_broker_articles_listing_group_id", "broker_articles", ["listing_group_id"]
    )
    op.create_table(
        "broker_article_snapshots",
        uuid_pk(),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("broker_article_id", sa.Uuid(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("description_hash", sa.String(64)),
        utc_column("verified_at", nullable=True),
        utc_column("captured_at"),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["broker_article_id"], ["broker_articles.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "run_id", "broker_article_id", name="uq_broker_article_snapshots_run_id"
        ),
    )
    op.create_index(
        "ix_broker_article_snapshots_run_id", "broker_article_snapshots", ["run_id"]
    )
    op.create_index(
        "ix_broker_article_snapshots_broker_article_id",
        "broker_article_snapshots",
        ["broker_article_id"],
    )
    op.create_table(
        "listing_aggregates",
        uuid_pk(),
        sa.Column("listing_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("option_tags_json", sa.JSON(), nullable=False),
        sa.Column("move_in_summary", sa.Text(), nullable=False),
        sa.Column("management_fee_summary", sa.Text(), nullable=False),
        sa.Column("room_bath_summary", sa.Text(), nullable=False),
        sa.Column("loan_summary", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_snapshot_id"], ["listing_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "listing_snapshot_id", name="uq_listing_aggregates_listing_snapshot_id"
        ),
    )
    op.create_table(
        "market_detail_snapshots",
        uuid_pk(),
        sa.Column("listing_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("finance_json", sa.JSON(), nullable=False),
        sa.Column("transactions_json", sa.JSON(), nullable=False),
        sa.Column("costs_json", sa.JSON(), nullable=False),
        sa.Column("maintenance_json", sa.JSON(), nullable=False),
        sa.Column("location_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_snapshot_id"], ["listing_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "listing_snapshot_id", name="uq_market_detail_snapshots_listing_snapshot_id"
        ),
    )
    op.create_table(
        "change_events",
        uuid_pk(),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("listing_group_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("changed_fields_json", sa.JSON(), nullable=False),
        sa.Column("before_json", sa.JSON()),
        sa.Column("after_json", sa.JSON()),
        utc_column("detected_at"),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["listing_group_id"], ["listing_groups.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_change_events_run_id", "change_events", ["run_id"])
    op.create_index(
        "ix_change_events_listing_group_id", "change_events", ["listing_group_id"]
    )
    op.create_table(
        "crawl_schedules",
        uuid_pk(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        utc_column("next_run_at"),
        sa.CheckConstraint(
            "cadence IN ('daily','weekdays','weekly')",
            name="ck_crawl_schedules_cadence_values",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tracked_sources.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_crawl_schedules_source_id", "crawl_schedules", ["source_id"])


def downgrade() -> None:
    for table_name in (
        "crawl_schedules",
        "change_events",
        "market_detail_snapshots",
        "listing_aggregates",
        "broker_article_snapshots",
        "broker_articles",
        "listing_snapshots",
        "apartment_snapshots",
        "listing_groups",
        "crawl_runs",
        "apartments",
        "tracked_sources",
    ):
        op.drop_table(table_name)
