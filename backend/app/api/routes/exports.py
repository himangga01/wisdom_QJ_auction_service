from datetime import date
from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.api.dependencies.auth import current_user
from app.models import User
from app.services.export_service import ExportNotFoundError, ExportService

router = APIRouter(prefix="/exports", tags=["exports"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def service(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> ExportService:
    return ExportService(session, user.id)


@router.get("/{source_id}.xlsx")
async def export_source(
    source_id: UUID,
    export_service: Annotated[ExportService, Depends(service)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> StreamingResponse:
    try:
        export_file = await export_service.generate(
            source_id, from_date=from_date, to_date=to_date
        )
    except ExportNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_export_range", "message": str(error)},
        ) from error
    return StreamingResponse(
        BytesIO(export_file.content),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{export_file.filename}"',
            "Cache-Control": "no-store",
        },
    )
