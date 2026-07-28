from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)

from app.api.dependencies.auth import (
    AuthContext,
    auth_error,
    clear_auth_cookies,
    current_auth,
    get_auth_service,
    require_allowed_origin,
)
from app.core.config import Settings, get_settings
from app.core.security import constant_time_equal
from app.schemas.auth import (
    AuthResponse,
    BootstrapRequest,
    BootstrapStatus,
    ChangePasswordRequest,
    LoginRequest,
    UserResponse,
)
from app.services.auth_service import (
    AccountInactiveError,
    AuthService,
    BootstrapCompletedError,
    BootstrapUnavailableError,
    InvalidCredentialsError,
    LoginResult,
    UserConflictError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response,
    result: LoginResult,
    settings: Settings,
) -> None:
    max_age = max(
        0,
        int((result.session.expires_at - datetime.now(timezone.utc)).total_seconds()),
    )
    response.set_cookie(
        "wisdom_session",
        result.session_token,
        max_age=max_age,
        expires=result.session.expires_at,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        "wisdom_csrf",
        result.csrf_token,
        max_age=max_age,
        expires=result.session.expires_at,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite="strict",
    )


def _auth_response(result: LoginResult) -> AuthResponse:
    return AuthResponse(
        user=UserResponse.model_validate(result.user),
        expires_at=result.session.expires_at,
    )


@router.get("/bootstrap-status", response_model=BootstrapStatus)
async def bootstrap_status(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> BootstrapStatus:
    return BootstrapStatus(bootstrap_required=await service.bootstrap_required())


@router.post(
    "/bootstrap",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_allowed_origin)],
)
async def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    bootstrap_token: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
) -> AuthResponse:
    configured_token = settings.auth_bootstrap_token
    if (
        len(configured_token) < 32
        or bootstrap_token is None
        or not constant_time_equal(configured_token, bootstrap_token)
    ):
        raise auth_error(
            "bootstrap_not_found",
            "요청한 리소스를 찾을 수 없습니다.",
            status.HTTP_404_NOT_FOUND,
        )
    try:
        await service.bootstrap_admin(
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
        )
        result = await service.login(payload.email, payload.password)
    except BootstrapCompletedError as error:
        raise auth_error(error.code, str(error), status.HTTP_409_CONFLICT) from error
    except BootstrapUnavailableError as error:
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_409_CONFLICT,
        ) from error
    except UserConflictError as error:
        raise auth_error(error.code, str(error), status.HTTP_409_CONFLICT) from error
    except ValueError as error:
        raise auth_error(
            "invalid_auth_input",
            str(error),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from error
    _set_auth_cookies(response, result, settings)
    return _auth_response(result)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(require_allowed_origin)],
)
async def login(
    payload: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    try:
        result = await service.login(payload.email, payload.password)
    except (InvalidCredentialsError, AccountInactiveError) as error:
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_401_UNAUTHORIZED,
        ) from error
    _set_auth_cookies(response, result, settings)
    return _auth_response(result)


@router.get("/me", response_model=AuthResponse)
async def me(
    context: Annotated[AuthContext, Depends(current_auth)],
) -> AuthResponse:
    return AuthResponse(
        user=UserResponse.model_validate(context.user),
        expires_at=context.session.expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    context: Annotated[AuthContext, Depends(current_auth)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await service.revoke_session(context.session)
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    context: Annotated[AuthContext, Depends(current_auth)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    try:
        await service.change_password(
            context.user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCredentialsError as error:
        raise auth_error(
            error.code,
            str(error),
            status.HTTP_400_BAD_REQUEST,
        ) from error
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT

