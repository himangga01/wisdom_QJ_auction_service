from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.apartment import ApartmentDetail, ApartmentHistoryPoint, ApartmentPage
from app.schemas.listing import ListingPage
from app.services.query_service import QueryNotFoundError, QueryService

router = APIRouter(prefix="/apartments", tags=["apartments"])


def service(session: Annotated[AsyncSession, Depends(get_session)]) -> QueryService:
    return QueryService(session)


def not_found(error: QueryNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": error.code, "message": str(error)},
    )


@router.get("", response_model=ApartmentPage)
async def get_apartments(
    query_service: Annotated[QueryService, Depends(service)],
    query: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> ApartmentPage:
    return await query_service.apartments(
        query=query, page=page, page_size=page_size
    )


@router.get("/{complex_id}", response_model=ApartmentDetail)
async def get_apartment(
    complex_id: str,
    query_service: Annotated[QueryService, Depends(service)],
) -> ApartmentDetail:
    try:
        return await query_service.apartment(complex_id)
    except QueryNotFoundError as error:
        raise not_found(error) from error


@router.get("/{complex_id}/history", response_model=list[ApartmentHistoryPoint])
async def get_apartment_history(
    complex_id: str,
    query_service: Annotated[QueryService, Depends(service)],
) -> list[ApartmentHistoryPoint]:
    try:
        return await query_service.history(complex_id)
    except QueryNotFoundError as error:
        raise not_found(error) from error


@router.get("/{complex_id}/listings", response_model=ListingPage)
async def get_apartment_listings(
    complex_id: str,
    query_service: Annotated[QueryService, Depends(service)],
    run_id: Annotated[UUID | None, Query(alias="runId")] = None,
    trade_type: Annotated[
        Literal["sale", "jeonse", "monthly"] | None,
        Query(alias="tradeType"),
    ] = None,
    listing_status: Annotated[
        Literal["active", "new", "changed", "removed"] | None,
        Query(alias="status"),
    ] = None,
) -> ListingPage:
    try:
        return await query_service.listings(
            complex_id,
            run_id=run_id,
            trade_type=trade_type,
            status=listing_status,
        )
    except QueryNotFoundError as error:
        raise not_found(error) from error

