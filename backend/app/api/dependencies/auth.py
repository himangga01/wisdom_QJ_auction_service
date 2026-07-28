from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models import AuthSession, User
from app.services.auth_service import (
    AccountInactiveError,
    AuthService,
    AuthenticationRequiredError,
    CsrfInvalidError,
)

MUTATING_METHODS = {"POST", "PATCH", "DELETE"}


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


def auth_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("wisdom_session", path="/", samesite="lax")
    response.delete_cookie("wisdom_csrf", path="/", samesite="strict")


def require_allowed_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    origin = request.headers.get("origin")
    if origin is None or origin.rstrip("/") not in {
        allowed.rstrip("/") for allowed in settings.auth_allowed_origins
    }:
        raise auth_error(
            "origin_invalid",
            "허용되지 않은 요청 출처입니다.",
            status.HTTP_403_FORBIDDEN,
        )


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        session,
        session_ttl=timedelta(hours=settings.auth_session_ttl_hours),
    )


async def current_auth(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthContext:
    if request.method in MUTATING_METHODS:
        require_allowed_origin(request, settings)
    try:
        user, auth_session = await service.authenticate(
            request.cookies.get("wisdom_session")
        )
        if request.method in MUTATING_METHODS:
            service.validate_csrf(
                auth_session,
                csrf_cookie=request.cookies.get("wisdom_csrf"),
                csrf_header=request.headers.get("x-csrf-token"),
            )
        return AuthContext(user=user, session=auth_session)
    except AccountInactiveError as error:
        clear_auth_cookies(response)
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_401_UNAUTHORIZED,
        ) from error
    except AuthenticationRequiredError as error:
        clear_auth_cookies(response)
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_401_UNAUTHORIZED,
        ) from error
    except CsrfInvalidError as error:
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_403_FORBIDDEN,
        ) from error


def current_user(
    context: Annotated[AuthContext, Depends(current_auth)],
) -> User:
    return context.user


def current_admin(
    context: Annotated[AuthContext, Depends(current_auth)],
) -> User:
    if context.user.role != "admin":
        raise auth_error(
            "admin_required",
            "관리자 권한이 필요합니다.",
            status.HTTP_403_FORBIDDEN,
        )
    return context.user

