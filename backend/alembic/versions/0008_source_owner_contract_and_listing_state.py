"""Finalize source ownership and add source-specific listing lifecycle state."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0008_source_owner_state"
down_revision: str | None = "0007_auth_principal_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _legacy_owner_server_default(dialect_name: str) -> sa.TextClause:
    stored_value = (
        LEGACY_SYSTEM_USER_ID.hex
        if dialect_name == "sqlite"
        else str(LEGACY_SYSTEM_USER_ID)
    )
    return sa.text(f"'{stored_value}'")


def _assert_global_url_hashes_unique(bind) -> None:
    tracked_sources = sa.table(
        "tracked_sources",
        sa.column("url_hash", sa.String()),
    )
    duplicate = bind.execute(
        sa.select(
            tracked_sources.c.url_hash,
            sa.func.count().label("duplicate_count"),
        )
        .group_by(tracked_sources.c.url_hash)
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "cannot downgrade: duplicate tracked source URL hashes "
            "exist across owners"
        )


def _backfill_source_listing_states() -> None:
    bind = op.get_bind()
    runs = sa.table(
        "crawl_runs",
        sa.column("id", sa.Uuid()),
        sa.column("source_id", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("finished_at", sa.DateTime(timezone=True)),
    )
    snapshots = sa.table(
        "listing_snapshots",
        sa.column("run_id", sa.Uuid()),
        sa.column("listing_group_id", sa.Uuid()),
        sa.column("captured_at", sa.DateTime(timezone=True)),
    )
    states = sa.table(
        "source_listing_states",
        sa.column("id", sa.Uuid()),
        sa.column("source_id", sa.Uuid()),
        sa.column("listing_group_id", sa.Uuid()),
        sa.column("visibility_state", sa.String()),
        sa.column("missing_count", sa.Integer()),
        sa.column("first_seen_at", sa.DateTime(timezone=True)),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
        sa.column("removed_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    run_rows = bind.execute(
        sa.select(
            runs.c.id,
            runs.c.source_id,
            runs.c.status,
            runs.c.created_at,
            runs.c.finished_at,
        )
        .where(runs.c.status.in_(("completed", "partial")))
        .order_by(runs.c.source_id, runs.c.created_at, runs.c.id)
    ).all()
    snapshots_by_run: dict[UUID, list[tuple[UUID, datetime]]] = {}
    for run_id, listing_group_id, captured_at in bind.execute(
        sa.select(
            snapshots.c.run_id,
            snapshots.c.listing_group_id,
            snapshots.c.captured_at,
        ).order_by(snapshots.c.run_id, snapshots.c.captured_at, snapshots.c.listing_group_id)
    ):
        snapshots_by_run.setdefault(run_id, []).append(
            (listing_group_id, captured_at)
        )

    lifecycle: dict[
        tuple[UUID, UUID],
        dict[str, object],
    ] = {}
    for run_id, source_id, status, created_at, finished_at in run_rows:
        observed: dict[UUID, datetime] = {}
        for listing_group_id, captured_at in snapshots_by_run.get(run_id, []):
            previous = observed.get(listing_group_id)
            if previous is None or captured_at > previous:
                observed[listing_group_id] = captured_at

        for listing_group_id, captured_at in observed.items():
            key = (source_id, listing_group_id)
            state = lifecycle.get(key)
            if state is None:
                lifecycle[key] = {
                    "id": uuid4(),
                    "source_id": source_id,
                    "listing_group_id": listing_group_id,
                    "visibility_state": "active",
                    "missing_count": 0,
                    "first_seen_at": captured_at,
                    "last_seen_at": captured_at,
                    "removed_at": None,
                    "updated_at": captured_at,
                }
                continue
            state["visibility_state"] = "active"
            state["missing_count"] = 0
            state["last_seen_at"] = captured_at
            state["removed_at"] = None
            state["updated_at"] = captured_at

        if status != "completed":
            continue
        observed_ids = set(observed)
        transition_at = finished_at or created_at
        for (state_source_id, listing_group_id), state in lifecycle.items():
            if state_source_id != source_id or listing_group_id in observed_ids:
                continue
            missing_count = int(state["missing_count"]) + 1
            state["missing_count"] = missing_count
            state["visibility_state"] = (
                "removed" if missing_count >= 2 else "missing"
            )
            state["removed_at"] = transition_at if missing_count >= 2 else None
            state["updated_at"] = transition_at

    if lifecycle:
        bind.execute(sa.insert(states), list(lifecycle.values()))


def upgrade() -> None:
    with op.batch_alter_table("tracked_sources") as batch_op:
        batch_op.alter_column(
            "owner_user_id",
            existing_type=sa.Uuid(),
            nullable=False,
            server_default=None,
        )
        batch_op.drop_constraint(
            "uq_tracked_sources_url_hash",
            type_="unique",
        )

    op.create_table(
        "source_listing_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("listing_group_id", sa.Uuid(), nullable=False),
        sa.Column("visibility_state", sa.String(length=20), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "visibility_state IN ('active','missing','removed')",
            name="ck_source_listing_states_visibility_state_values",
        ),
        sa.CheckConstraint(
            "missing_count >= 0",
            name="ck_source_listing_states_missing_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["tracked_sources.id"],
            name="fk_source_listing_states_source_id_tracked_sources",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_group_id"],
            ["listing_groups.id"],
            name="fk_source_listing_states_listing_group_id_listing_groups",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_listing_states"),
        sa.UniqueConstraint(
            "source_id",
            "listing_group_id",
            name="uq_source_listing_states_source_listing_group",
        ),
    )
    op.create_index(
        "ix_source_listing_states_source_id",
        "source_listing_states",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_listing_states_listing_group_id",
        "source_listing_states",
        ["listing_group_id"],
        unique=False,
    )
    _backfill_source_listing_states()


def downgrade() -> None:
    bind = op.get_bind()
    _assert_global_url_hashes_unique(bind)

    op.drop_index(
        "ix_source_listing_states_listing_group_id",
        table_name="source_listing_states",
    )
    op.drop_index(
        "ix_source_listing_states_source_id",
        table_name="source_listing_states",
    )
    op.drop_table("source_listing_states")

    with op.batch_alter_table("tracked_sources") as batch_op:
        batch_op.create_unique_constraint(
            "uq_tracked_sources_url_hash",
            ["url_hash"],
        )
        batch_op.alter_column(
            "owner_user_id",
            existing_type=sa.Uuid(),
            nullable=True,
            server_default=_legacy_owner_server_default(bind.dialect.name),
        )
