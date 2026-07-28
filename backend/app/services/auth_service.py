from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    constant_time_equal,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import AuthSession, TrackedSource, User
from app.models.user import LEGACY_SYSTEM_USER_EMAIL, LEGACY_SYSTEM_USER_ID


class AuthError(Exception):
    code = "authentication_error"


class BootstrapCompletedError(AuthError):
    code = "bootstrap_completed"


class BootstrapUnavailableError(AuthError):
    code = "bootstrap_unavailable"


class InvalidCredentialsError(AuthError):
    code = "invalid_credentials"


class AuthenticationRequiredError(AuthError):
    code = "authentication_required"


class AccountInactiveError(AuthError):
    code = "account_inactive"


class CsrfInvalidError(AuthError):
    code = "csrf_invalid"


class UserConflictError(AuthError):
    code = "user_conflict"


class UserNotFoundError(AuthError):
    code = "user_not_found"


class LastActiveAdminError(AuthError):
    code = "last_active_admin"


class SystemUserImmutableError(AuthError):
    code = "system_user_immutable"


@dataclass(frozen=True)
class LoginResult:
    user: User
    session: AuthSession
    session_token: str
    csrf_token: str


_DUMMY_PASSWORD_HASH = hash_password("wisdom authentication timing sentinel")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AuthService:
    def __init__(self, session: AsyncSession, *, session_ttl: timedelta) -> None:
        self.session = session
        self.session_ttl = session_ttl

    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if (
            not normalized
            or len(normalized) > 320
            or normalized.startswith("@")
            or normalized.endswith("@")
            or "@" not in normalized
        ):
            raise ValueError("유효한 이메일 주소가 필요합니다.")
        return normalized

    @staticmethod
    def validate_password(password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise ValueError("비밀번호는 12자 이상 128자 이하여야 합니다.")

    async def bootstrap_required(self) -> bool:
        human_admin_count = await self.session.scalar(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.is_system.is_(False),
            )
        )
        return not bool(human_admin_count)

    async def ensure_legacy_system_user(self, *, commit: bool = True) -> User:
        legacy = await self.session.get(User, LEGACY_SYSTEM_USER_ID)
        if legacy is None:
            legacy = User(
                id=LEGACY_SYSTEM_USER_ID,
                email=LEGACY_SYSTEM_USER_EMAIL,
                display_name="Legacy system owner",
                password_hash=None,
                role="member",
                is_active=False,
                is_system=True,
            )
            self.session.add(legacy)
            await self.session.flush()
        if commit:
            await self.session.commit()
        return legacy

    async def bootstrap_admin(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
    ) -> User:
        normalized_email = self.normalize_email(email)
        self.validate_password(password)
        if not display_name.strip():
            raise ValueError("표시 이름이 필요합니다.")
        try:
            legacy = await self.session.scalar(
                select(User)
                .where(User.id == LEGACY_SYSTEM_USER_ID)
                .with_for_update()
            )
            if legacy is None:
                legacy = await self.ensure_legacy_system_user(commit=False)
            if not await self.bootstrap_required():
                raise BootstrapCompletedError("최초 관리자 생성이 이미 완료되었습니다.")
            existing = await self.session.scalar(
                select(User.id).where(User.email == normalized_email)
            )
            if existing is not None:
                raise UserConflictError("이미 사용 중인 이메일입니다.")

            admin = User(
                email=normalized_email,
                display_name=display_name.strip(),
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
                is_system=False,
            )
            self.session.add(admin)
            await self.session.flush()
            await self.session.execute(
                update(TrackedSource)
                .where(
                    or_(
                        TrackedSource.owner_user_id.is_(None),
                        TrackedSource.owner_user_id == legacy.id,
                    )
                )
                .values(owner_user_id=admin.id)
            )
            remaining = await self.session.scalar(
                select(func.count(TrackedSource.id)).where(
                    or_(
                        TrackedSource.owner_user_id.is_(None),
                        TrackedSource.owner_user_id == legacy.id,
                    )
                )
            )
            if remaining:
                raise BootstrapUnavailableError(
                    "기존 조사 소유권을 최초 관리자에게 이전하지 못했습니다."
                )
            await self.session.commit()
            return admin
        except Exception:
            await self.session.rollback()
            raise

    async def login(
        self,
        email: str,
        password: str,
        *,
        now: datetime | None = None,
    ) -> LoginResult:
        current_time = now or _utc_now()
        try:
            normalized_email = self.normalize_email(email)
        except ValueError:
            normalized_email = ""
        user = await self.session.scalar(
            select(User)
            .where(User.email == normalized_email)
            .with_for_update()
        )
        if user is None or user.is_system or user.password_hash is None:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError(
                "이메일 또는 비밀번호가 올바르지 않습니다."
            )
        if (
            user.locked_until is not None
            and _aware_utc(user.locked_until) > current_time
        ):
            raise InvalidCredentialsError(
                "이메일 또는 비밀번호가 올바르지 않습니다."
            )
        if not user.is_active:
            raise AccountInactiveError("비활성화된 계정입니다.")
        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.locked_until = current_time + timedelta(minutes=15)
            await self.session.commit()
            raise InvalidCredentialsError(
                "이메일 또는 비밀번호가 올바르지 않습니다."
            )

        user.failed_login_count = 0
        user.locked_until = None
        session_token = generate_token()
        csrf_token = generate_token()
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(session_token),
            csrf_hash=hash_token(csrf_token),
            created_at=current_time,
            last_seen_at=current_time,
            expires_at=current_time + self.session_ttl,
        )
        self.session.add(auth_session)
        await self.session.commit()
        return LoginResult(user, auth_session, session_token, csrf_token)

    async def authenticate(
        self,
        session_token: str | None,
        *,
        now: datetime | None = None,
    ) -> tuple[User, AuthSession]:
        if not session_token:
            raise AuthenticationRequiredError("로그인이 필요합니다.")
        row = (
            await self.session.execute(
                select(User, AuthSession)
                .join(AuthSession, AuthSession.user_id == User.id)
                .where(AuthSession.token_hash == hash_token(session_token))
            )
        ).first()
        if row is None:
            raise AuthenticationRequiredError("로그인이 필요합니다.")
        user, auth_session = row
        current_time = now or _utc_now()
        if (
            auth_session.revoked_at is not None
            or _aware_utc(auth_session.expires_at) <= current_time
        ):
            raise AuthenticationRequiredError("로그인이 필요합니다.")
        if not user.is_active or user.is_system:
            raise AccountInactiveError("비활성화된 계정입니다.")
        auth_session.last_seen_at = current_time
        await self.session.commit()
        return user, auth_session

    @staticmethod
    def validate_csrf(
        auth_session: AuthSession,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> None:
        if (
            not csrf_cookie
            or not csrf_header
            or not constant_time_equal(csrf_cookie, csrf_header)
            or not constant_time_equal(
                hash_token(csrf_header),
                auth_session.csrf_hash,
            )
        ):
            raise CsrfInvalidError("CSRF 토큰이 올바르지 않습니다.")

    async def revoke_session(
        self,
        auth_session: AuthSession,
        *,
        now: datetime | None = None,
    ) -> None:
        auth_session.revoked_at = now or _utc_now()
        await self.session.commit()

    async def revoke_all_sessions(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now or _utc_now())
        )

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        self.validate_password(new_password)
        if user.password_hash is None or not verify_password(
            current_password, user.password_hash
        ):
            raise InvalidCredentialsError("현재 비밀번호가 올바르지 않습니다.")
        user.password_hash = hash_password(new_password)
        await self.revoke_all_sessions(user.id)
        await self.session.commit()

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        query: str,
    ) -> tuple[list[User], int]:
        filters = [User.is_system.is_(False)]
        normalized_query = query.strip().lower()
        if normalized_query:
            filters.append(
                or_(
                    func.lower(User.email).contains(normalized_query),
                    func.lower(User.display_name).contains(normalized_query),
                )
            )
        total = await self.session.scalar(
            select(func.count(User.id)).where(*filters)
        )
        users = list(
            (
                await self.session.scalars(
                    select(User)
                    .where(*filters)
                    .order_by(User.created_at, User.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return users, int(total or 0)

    async def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        role: str,
    ) -> User:
        normalized_email = self.normalize_email(email)
        self.validate_password(password)
        if role not in ("admin", "member"):
            raise ValueError("role은 admin 또는 member여야 합니다.")
        if not display_name.strip():
            raise ValueError("표시 이름이 필요합니다.")
        if await self.session.scalar(
            select(User.id).where(User.email == normalized_email)
        ):
            raise UserConflictError("이미 사용 중인 이메일입니다.")
        user = User(
            email=normalized_email,
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            is_system=False,
        )
        self.session.add(user)
        await self.session.commit()
        return user

    async def get_human_user(self, user_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None or user.is_system:
            raise UserNotFoundError("사용자를 찾을 수 없습니다.")
        return user

    async def _protect_last_admin(
        self,
        user: User,
        *,
        role: str | None,
        is_active: bool | None,
    ) -> None:
        removes_active_admin = (
            user.role == "admin"
            and user.is_active
            and (role == "member" or is_active is False)
        )
        if not removes_active_admin:
            return
        active_admin_ids = list(
            (
                await self.session.scalars(
                    select(User.id)
                    .where(
                        User.role == "admin",
                        User.is_active.is_(True),
                        User.is_system.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        remaining = any(
            admin_id != user.id
            for admin_id in active_admin_ids
        )
        if not remaining:
            raise LastActiveAdminError(
                "마지막 활성 관리자는 비활성화하거나 강등할 수 없습니다."
            )

    async def update_user(
        self,
        user: User,
        *,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        if user.is_system:
            raise SystemUserImmutableError("시스템 사용자는 변경할 수 없습니다.")
        if role is not None and role not in ("admin", "member"):
            raise ValueError("role은 admin 또는 member여야 합니다.")
        await self._protect_last_admin(user, role=role, is_active=is_active)
        if display_name is not None:
            if not display_name.strip():
                raise ValueError("표시 이름이 필요합니다.")
            user.display_name = display_name.strip()
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
            if not is_active:
                await self.revoke_all_sessions(user.id)
        await self.session.commit()
        return user

    async def set_temporary_password(self, user: User, password: str) -> None:
        if user.is_system:
            raise SystemUserImmutableError("시스템 사용자는 변경할 수 없습니다.")
        self.validate_password(password)
        user.password_hash = hash_password(password)
        await self.revoke_all_sessions(user.id)
        await self.session.commit()
