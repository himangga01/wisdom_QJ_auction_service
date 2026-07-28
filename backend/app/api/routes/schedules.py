from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domain.url_identity import InvalidSourceUrl
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleDelete,
    SchedulePatch,
    ScheduleResponse,
    ScheduleRuns,
)
from app.services.schedule_service import (
    ScheduleConflictError,
    ScheduleDeleteConflictError,
    ScheduleNotFoundError,
    ScheduleService,
    ScheduleSourceNotFoundError,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> ScheduleService:
    return ScheduleService(session)


def api_error(error: Exception, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "code": getattr(error, "code", "invalid_schedule"),
            "message": str(error),
        },
    )


@router.get("", response_model=list[ScheduleResponse])
async def get_schedules(
    schedule_service: Annotated[ScheduleService, Depends(service)],
) -> list[ScheduleResponse]:
    return await schedule_service.list()


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    schedule_service: Annotated[ScheduleService, Depends(service)],
) -> ScheduleResponse:
    try:
        return await schedule_service.create(payload)
    except (InvalidSourceUrl, ValueError) as error:
        raise api_error(error, status.HTTP_422_UNPROCESSABLE_ENTITY) from error
    except ScheduleSourceNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    except ScheduleConflictError as error:
        raise api_error(error, status.HTTP_409_CONFLICT) from error


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def patch_schedule(
    schedule_id: UUID,
    payload: SchedulePatch,
    schedule_service: Annotated[ScheduleService, Depends(service)],
) -> ScheduleResponse:
    try:
        return await schedule_service.patch(schedule_id, payload)
    except ScheduleNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    except ValueError as error:
        raise api_error(error, status.HTTP_422_UNPROCESSABLE_ENTITY) from error


@router.delete("/{schedule_id}", response_model=ScheduleDelete)
async def delete_schedule(
    schedule_id: UUID,
    schedule_service: Annotated[ScheduleService, Depends(service)],
    hard: Annotated[bool, Query()] = False,
) -> ScheduleDelete:
    try:
        return await schedule_service.delete(schedule_id, hard=hard)
    except ScheduleNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    except ScheduleDeleteConflictError as error:
        raise api_error(error, status.HTTP_409_CONFLICT) from error


@router.get("/{schedule_id}/runs", response_model=ScheduleRuns)
async def get_schedule_runs(
    schedule_id: UUID,
    schedule_service: Annotated[ScheduleService, Depends(service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScheduleRuns:
    try:
        return await schedule_service.runs(schedule_id, limit=limit)
    except ScheduleNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error

