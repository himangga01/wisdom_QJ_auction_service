from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import current_user
from app.core.database import get_session
from app.models import User
from app.schemas.notification import (
    NotificationPreference,
    NotificationPreferencePatch,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationService,
)

router = APIRouter(prefix="/sources", tags=["notification-preferences"])


def service(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> NotificationService:
    return NotificationService(session, user.id)


def not_found(error: NotificationNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": error.code, "message": str(error)},
    )


@router.get(
    "/{source_id}/notification-preference",
    response_model=NotificationPreference,
)
async def get_notification_preference(
    source_id: UUID,
    notification_service: Annotated[NotificationService, Depends(service)],
) -> NotificationPreference:
    try:
        return await notification_service.get_preference(source_id)
    except NotificationNotFoundError as error:
        raise not_found(error) from error


@router.patch(
    "/{source_id}/notification-preference",
    response_model=NotificationPreference,
)
async def patch_notification_preference(
    source_id: UUID,
    payload: NotificationPreferencePatch,
    notification_service: Annotated[NotificationService, Depends(service)],
) -> NotificationPreference:
    try:
        return await notification_service.update_preference(
            source_id,
            **payload.model_dump(),
        )
    except NotificationNotFoundError as error:
        raise not_found(error) from error
