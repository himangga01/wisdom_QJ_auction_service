"""Add authentication principals, sessions, and expandable source ownership."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "0007_auth_principal_owner"
down_revision: str | None = "0006_apartment_basic_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
LEGACY_SYSTEM_USER_EMAIL = "legacy-system@wisdom.invalid"


def _legacy_owner_server_default(dialect_name: str) -> sa.TextClause:
    stored_value = (
        LEGACY_SYSTEM_USER_ID.hex
        if dialect_name == "sqlite"
        else str(LEGACY_SYSTEM_USER_ID)
    )
    return sa.text(f"'{stored_value}'")


def upgrade() -> None:
    legacy_owner_default = _legacy_owner_server_default(
        op.get_bind().dialect.name
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin','member')",
            name="ck_users_role_values",
        ),
        sa.CheckConstraint(
            "failed_login_count >= 0",
            name="ck_users_failed_login_count_nonnegative",
        ),
        sa.CheckConstraint(
            "is_system OR password_hash IS NOT NULL",
            name="ck_users_human_password_required",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("role", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_system", sa.Boolean()),
        sa.column("failed_login_count", sa.Integer()),
        sa.column("locked_until", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        users,
        [
            {
                "id": LEGACY_SYSTEM_USER_ID,
                "email": LEGACY_SYSTEM_USER_EMAIL,
                "display_name": "Legacy system owner",
                "password_hash": None,
                "role": "member",
                "is_active": False,
                "is_system": True,
                "failed_login_count": 0,
                "locked_until": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_auth_sessions_token_hash",
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_id",
        "auth_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        ["expires_at"],
        unique=False,
    )

    with op.batch_alter_table("tracked_sources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_user_id",
                sa.Uuid(),
                nullable=True,
                server_default=legacy_owner_default,
            )
        )
        batch_op.create_foreign_key(
            "fk_tracked_sources_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_tracked_sources_owner_user_id",
            ["owner_user_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_tracked_sources_owner_url_hash",
            ["owner_user_id", "url_hash"],
        )

    tracked_sources = sa.table(
        "tracked_sources",
        sa.column("owner_user_id", sa.Uuid()),
    )
    op.execute(
        tracked_sources.update()
        .where(tracked_sources.c.owner_user_id.is_(None))
        .values(owner_user_id=LEGACY_SYSTEM_USER_ID)
    )


def downgrade() -> None:
    with op.batch_alter_table("tracked_sources") as batch_op:
        batch_op.drop_constraint(
            "uq_tracked_sources_owner_url_hash",
            type_="unique",
        )
        batch_op.drop_index("ix_tracked_sources_owner_user_id")
        batch_op.drop_constraint(
            "fk_tracked_sources_owner_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("owner_user_id")

    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
