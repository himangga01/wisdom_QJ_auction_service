from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import current_user
from app.core.database import get_session
from app.models import User
from app.schemas.notification import (
    NotificationPage,
    NotificationReadAll,
    NotificationReadPatch,
    NotificationUnreadCount,
)
from app.services.notification_service import (
    InvalidNotificationCursorError,
    NotificationNotFoundError,
    NotificationService,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def service(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> NotificationService:
    return NotificationService(session, user.id)


def api_error(error: Exception, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "code": getattr(error, "code", "notification_error"),
            "message": str(error),
        },
    )


@router.get("", response_model=NotificationPage)
async def get_notifications(
    notification_service: Annotated[NotificationService, Depends(service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: Annotated[bool, Query(alias="unreadOnly")] = False,
) -> NotificationPage:
    try:
        return await notification_service.list(
            cursor=cursor,
            limit=limit,
            unread_only=unread_only,
        )
    except InvalidNotificationCursorError as error:
        raise api_error(error, status.HTTP_422_UNPROCESSABLE_ENTITY) from error


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def get_unread_count(
    notification_service: Annotated[NotificationService, Depends(service)],
) -> NotificationUnreadCount:
    return NotificationUnreadCount(
        count=await notification_service.unread_count()
    )


@router.patch("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_notification(
    notification_id: UUID,
    payload: NotificationReadPatch,
    notification_service: Annotated[NotificationService, Depends(service)],
) -> Response:
    try:
        await notification_service.mark_read(notification_id, read=payload.read)
    except NotificationNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read-all", response_model=NotificationReadAll)
async def read_all_notifications(
    notification_service: Annotated[NotificationService, Depends(service)],
) -> NotificationReadAll:
    return NotificationReadAll(
        updated_count=await notification_service.read_all()
    )
