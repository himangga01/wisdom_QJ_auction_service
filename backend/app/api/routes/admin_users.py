from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth import auth_error, current_admin, get_auth_service
from app.models import User
from app.schemas.auth import (
    AdminUserCreate,
    AdminUserPage,
    AdminUserPatch,
    AdminUserResponse,
    TemporaryPasswordRequest,
    TemporaryPasswordResponse,
)
from app.services.auth_service import (
    AuthService,
    LastActiveAdminError,
    SystemUserImmutableError,
    UserConflictError,
    UserNotFoundError,
)

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(current_admin)],
)


def _raise_auth_service_error(error: Exception) -> None:
    if isinstance(error, UserNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, (UserConflictError, LastActiveAdminError)):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(error, (SystemUserImmutableError, ValueError)):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        raise error
    raise auth_error(
        getattr(error, "code", "invalid_auth_input"),
        str(error),
        http_status,
    ) from error


@router.get("", response_model=AdminUserPage)
async def list_users(
    service: Annotated[AuthService, Depends(get_auth_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    query: Annotated[str, Query(max_length=320)] = "",
) -> AdminUserPage:
    users, total = await service.list_users(
        page=page,
        page_size=page_size,
        query=query,
    )
    return AdminUserPage(
        items=[AdminUserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: AdminUserCreate,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AdminUserResponse:
    try:
        user = await service.create_user(
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
        )
    except (UserConflictError, ValueError) as error:
        _raise_auth_service_error(error)
    return AdminUserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    payload: AdminUserPatch,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AdminUserResponse:
    try:
        user = await service.get_human_user(user_id)
        user = await service.update_user(
            user,
            display_name=payload.display_name,
            role=payload.role,
            is_active=payload.is_active,
        )
    except (
        LastActiveAdminError,
        SystemUserImmutableError,
        UserNotFoundError,
        ValueError,
    ) as error:
        _raise_auth_service_error(error)
    return AdminUserResponse.model_validate(user)


@router.post(
    "/{user_id}/temporary-password",
    response_model=TemporaryPasswordResponse,
)
async def temporary_password(
    user_id: UUID,
    payload: TemporaryPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TemporaryPasswordResponse:
    try:
        user = await service.get_human_user(user_id)
        await service.set_temporary_password(user, payload.password)
    except (SystemUserImmutableError, UserNotFoundError, ValueError) as error:
        _raise_auth_service_error(error)
    return TemporaryPasswordResponse(user_id=user_id)

