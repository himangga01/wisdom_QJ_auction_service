from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.api.dependencies.auth import current_user
from app.models import User
from app.schemas.listing import ListingDetail
from app.services.query_service import QueryNotFoundError, QueryService

router = APIRouter(prefix="/listings", tags=["listings"])


def service(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> QueryService:
    return QueryService(session, user.id)


@router.get("/{listing_group_id}", response_model=ListingDetail)
async def get_listing(
    listing_group_id: UUID,
    query_service: Annotated[QueryService, Depends(service)],
    source_id: Annotated[UUID, Query(alias="sourceId")],
    run_id: Annotated[UUID | None, Query(alias="runId")] = None,
) -> ListingDetail:
    try:
        return await query_service.listing(
            listing_group_id,
            source_id=source_id,
            run_id=run_id,
        )
    except QueryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": error.code, "message": str(error)},
        ) from error
