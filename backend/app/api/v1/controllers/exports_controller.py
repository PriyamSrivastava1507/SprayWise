from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Query, Response

from app.api.deps import ExportServiceDep
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/scans", tags=["exports"])
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Scan or successful result not found"}}
MethodQuery = Annotated[Optional[Literal["classical", "ml"]], Query()]


def _download(filename: str, data: bytes, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scan_id}/export/csv", responses=NOT_FOUND, response_class=Response)
def export_csv(scan_id: int, service: ExportServiceDep, method: MethodQuery = None) -> Response:
    filename, data = service.csv(scan_id, method)
    return _download(filename, data, "text/csv")


@router.get("/{scan_id}/export/pdf", responses=NOT_FOUND, response_class=Response)
def export_pdf(scan_id: int, service: ExportServiceDep, method: MethodQuery = None) -> Response:
    filename, data = service.pdf(scan_id, method)
    return _download(filename, data, "application/pdf")
