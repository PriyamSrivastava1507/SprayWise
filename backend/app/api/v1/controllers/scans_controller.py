"""Scan history: list, detail, delete."""

from typing import Annotated, Optional

from fastapi import APIRouter, Query, Response

from app.api.deps import ScanServiceDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.scan import ScanDetail

router = APIRouter(prefix="/scans", tags=["scans"])
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Scan not found"}}


@router.get("", response_model=Page[ScanDetail], summary="List scans, newest first")
def list_scans(
    service: ScanServiceDep,
    field_id: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ScanDetail]:
    return service.list(field_id, limit, offset)


@router.get("/{scan_id}", response_model=ScanDetail, responses=NOT_FOUND)
def get_scan(scan_id: int, service: ScanServiceDep) -> ScanDetail:
    return service.get(scan_id)


@router.delete("/{scan_id}", status_code=204, responses=NOT_FOUND)
def delete_scan(scan_id: int, service: ScanServiceDep) -> Response:
    service.delete(scan_id)
    return Response(status_code=204)
