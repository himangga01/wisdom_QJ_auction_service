from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.dashboard import DashboardResponse
from app.services.query_service import QueryNotFoundError, QueryService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> QueryService:
    return QueryService(session)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    query_service: Annotated[QueryService, Depends(service)],
    source_id: Annotated[UUID | None, Query(alias="sourceId")] = None,
) -> DashboardResponse:
    try:
        return await query_service.dashboard(source_id)
    except QueryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": error.code, "message": str(error)},
        ) from error

