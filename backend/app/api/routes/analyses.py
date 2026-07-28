from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.api.dependencies.auth import current_user
from app.api.routes.health import BrowserStatus, browser_status
from app.domain.url_identity import InvalidSourceUrl
from app.schemas.analysis import (
    AnalysisAccepted,
    AnalysisCancel,
    AnalysisCreate,
    AnalysisResult,
    AnalysisStatus,
)
from app.services.analysis_service import (
    AnalysisCannotCancelError,
    AnalysisNotFoundError,
    AnalysisNotReadyError,
    AnalysisOptionConflictError,
    AnalysisService,
    CrawlTaskDispatcher,
    QueueUnavailableError,
)
from app.runtime import get_crawl_dispatcher
from app.models import User

router = APIRouter(prefix="/analyses", tags=["analyses"])


def get_dispatcher() -> CrawlTaskDispatcher:
    return get_crawl_dispatcher()


def service(
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[CrawlTaskDispatcher, Depends(get_dispatcher)],
) -> AnalysisService:
    return AnalysisService(session, dispatcher)


def api_error(error: Exception, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "code": getattr(error, "code", "analysis_error"),
            "message": str(error),
        },
    )


@router.post("", response_model=AnalysisAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    payload: AnalysisCreate,
    user: Annotated[User, Depends(current_user)],
    analysis_service: Annotated[AnalysisService, Depends(service)],
    browser: Annotated[BrowserStatus, Depends(browser_status)],
) -> AnalysisAccepted:
    if browser == "unavailable":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "browser_unavailable",
                "message": "수집용 Chrome이 준비되지 않았습니다.",
            },
        )
    try:
        run, _ = await analysis_service.create_for_user(
            user.id,
            str(payload.source_url),
            collect_broker_details=payload.collect_broker_details,
            interaction_delay_preset=payload.interaction_delay_preset,
        )
    except InvalidSourceUrl as error:
        raise api_error(error, status.HTTP_422_UNPROCESSABLE_ENTITY) from error
    except AnalysisOptionConflictError as error:
        raise api_error(error, status.HTTP_409_CONFLICT) from error
    except QueueUnavailableError as error:
        raise api_error(error, status.HTTP_503_SERVICE_UNAVAILABLE) from error
    return AnalysisAccepted(
        run_id=run.id,
        source_id=run.source_id,
        status=run.status,
        collect_broker_details=run.collect_broker_details,
        interaction_delay_preset=run.interaction_delay_preset,
    )


@router.get("/{run_id}", response_model=AnalysisStatus)
async def get_analysis(
    run_id: UUID,
    analysis_service: Annotated[AnalysisService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> AnalysisStatus:
    try:
        run = await analysis_service.get(user.id, run_id)
    except AnalysisNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    return AnalysisStatus(
        run_id=run.id,
        source_id=run.source_id,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        error_code=run.error_code,
        started_at=run.started_at,
        finished_at=run.finished_at,
        collect_broker_details=run.collect_broker_details,
        interaction_delay_preset=run.interaction_delay_preset,
    )


@router.get("/{run_id}/result", response_model=AnalysisResult)
async def get_analysis_result(
    run_id: UUID,
    analysis_service: Annotated[AnalysisService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> AnalysisResult:
    try:
        run, apartment, snapshot = await analysis_service.result(user.id, run_id)
    except AnalysisNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    except AnalysisNotReadyError as error:
        raise api_error(error, status.HTTP_409_CONFLICT) from error
    return AnalysisResult(
        run_id=run.id,
        status=run.status,
        apartment_id=apartment.id,
        naver_complex_id=apartment.naver_complex_id,
        name=apartment.name,
        summary=snapshot.details_json,
    )


@router.post("/{run_id}/cancel", response_model=AnalysisCancel)
async def cancel_analysis(
    run_id: UUID,
    analysis_service: Annotated[AnalysisService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> AnalysisCancel:
    try:
        run = await analysis_service.cancel(user.id, run_id)
    except AnalysisNotFoundError as error:
        raise api_error(error, status.HTTP_404_NOT_FOUND) from error
    except AnalysisCannotCancelError as error:
        raise api_error(error, status.HTTP_409_CONFLICT) from error
    return AnalysisCancel(run_id=run.id, status="cancelled")
