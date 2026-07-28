from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.security import hash_password
from app.models import TrackedSource, User
from app.services.auth_service import (
    AuthService,
    BootstrapCompletedError,
    InvalidCredentialsError,
    LastActiveAdminError,
)


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_creates_first_admin_and_transfers_legacy_sources(
    session_factory,
) -> None:
    async with session_factory() as session:
        service = AuthService(session, session_ttl=timedelta(hours=12))
        legacy = await service.ensure_legacy_system_user()
        source = TrackedSource(
            source_url="https://fin.land.naver.com/map?a=1",
            normalized_url="https://fin.land.naver.com/map?a=1",
            url_hash="a" * 64,
            owner_user_id=legacy.id,
        )
        session.add(source)
        await session.commit()

        admin = await service.bootstrap_admin(
            email=" Admin@Example.COM ",
            display_name="관리자",
            password="correct horse battery staple",
        )
        await session.refresh(source)

        assert admin.email == "admin@example.com"
        assert admin.role == "admin"
        assert admin.is_system is False
        assert source.owner_user_id == admin.id
        with pytest.raises(BootstrapCompletedError):
            await service.bootstrap_admin(
                email="second@example.com",
                display_name="두 번째",
                password="correct horse battery staple",
            )


@pytest.mark.asyncio
async def test_five_failed_logins_lock_account_for_fifteen_minutes(
    session_factory,
) -> None:
    async with session_factory() as session:
        service = AuthService(session, session_ttl=timedelta(hours=12))
        user = User(
            email="member@example.com",
            display_name="회원",
            password_hash=hash_password("correct horse battery staple"),
            role="member",
        )
        session.add(user)
        await session.commit()
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)

        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                await service.login(
                    "member@example.com",
                    "wrong password",
                    now=now,
                )

        assert user.failed_login_count == 5
        assert user.locked_until == now + timedelta(minutes=15)
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                "member@example.com",
                "correct horse battery staple",
                now=now + timedelta(minutes=1),
            )


@pytest.mark.asyncio
async def test_password_change_revokes_every_existing_session(session_factory) -> None:
    async with session_factory() as session:
        service = AuthService(session, session_ttl=timedelta(hours=12))
        user = User(
            email="member@example.com",
            display_name="회원",
            password_hash=hash_password("correct horse battery staple"),
            role="member",
        )
        session.add(user)
        await session.commit()
        first = await service.login(
            user.email,
            "correct horse battery staple",
        )
        second = await service.login(
            user.email,
            "correct horse battery staple",
        )

        await service.change_password(
            user,
            current_password="correct horse battery staple",
            new_password="an even better password",
        )

        await session.refresh(first.session)
        await session.refresh(second.session)
        assert first.session.revoked_at is not None
        assert second.session.revoked_at is not None


@pytest.mark.asyncio
async def test_last_active_admin_cannot_be_disabled_or_demoted(session_factory) -> None:
    async with session_factory() as session:
        service = AuthService(session, session_ttl=timedelta(hours=12))
        admin = User(
            email="admin@example.com",
            display_name="관리자",
            password_hash=hash_password("correct horse battery staple"),
            role="admin",
        )
        session.add(admin)
        await session.commit()

        with pytest.raises(LastActiveAdminError):
            await service.update_user(admin, is_active=False)
        with pytest.raises(LastActiveAdminError):
            await service.update_user(admin, role="member")


class _ScalarIds:
    def __init__(self, values) -> None:
        self._values = values

    def all(self):
        return list(self._values)


class _LockRecordingSession:
    def __init__(self, *, user: User, remaining_admin_ids=()) -> None:
        self.user = user
        self.remaining_admin_ids = list(remaining_admin_ids)
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.user

    async def scalars(self, statement):
        self.statements.append(statement)
        return _ScalarIds(self.remaining_admin_ids)

    async def commit(self) -> None:
        return None

    def add(self, _value) -> None:
        return None


@pytest.mark.asyncio
async def test_login_locks_the_user_row_before_updating_failure_count() -> None:
    user = User(
        email="member@example.com",
        display_name="회원",
        password_hash=hash_password("correct horse battery staple"),
        role="member",
        is_active=True,
        failed_login_count=0,
    )
    session = _LockRecordingSession(user=user)
    service = AuthService(session, session_ttl=timedelta(hours=12))

    with pytest.raises(InvalidCredentialsError):
        await service.login("member@example.com", "wrong password")

    assert session.statements[0]._for_update_arg is not None


@pytest.mark.asyncio
async def test_last_admin_guard_locks_active_admin_rows_before_counting() -> None:
    admin = User(
        email="admin@example.com",
        display_name="관리자",
        password_hash=hash_password("correct horse battery staple"),
        role="admin",
        is_active=True,
    )
    other_admin_id = uuid4()
    session = _LockRecordingSession(
        user=admin,
        remaining_admin_ids=[admin.id, other_admin_id],
    )
    service = AuthService(session, session_ttl=timedelta(hours=12))

    await service._protect_last_admin(admin, role="member", is_active=None)

    assert any(
        statement._for_update_arg is not None
        for statement in session.statements
    )
