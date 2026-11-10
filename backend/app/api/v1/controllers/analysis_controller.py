"""POST /analyze: validate the upload, then hand off to the service."""

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import AnalysisServiceDep, SettingsDep
from app.core.exceptions import FileTooLargeError, InvalidImageError
from app.schemas.analysis import AnalyzeParams
from app.schemas.common import ErrorResponse
from app.schemas.scan import ScanDetail

router = APIRouter(tags=["analysis"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@router.post(
    "/analyze",
    response_model=ScanDetail,
    status_code=201,
    summary="Analyse a field photo",
    responses={
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Invalid image or parameters"},
        404: {"model": ErrorResponse, "description": "field_id does not exist"},
        503: {"model": ErrorResponse, "description": "ML model unavailable (ml mode)"},
    },
)
def analyze(
    service: AnalysisServiceDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="JPG or PNG photo")],
    mode: Annotated[Literal["classical", "ml", "compare"], Form()] = "classical",
    field_id: Annotated[Optional[str], Form()] = None,
    field_name: Annotated[Optional[str], Form()] = None,
    area_ha: Annotated[float, Form()] = 1.0,
    dose_l_per_ha: Annotated[float, Form()] = 2.0,
    price_per_l: Annotated[float, Form()] = 10.0,
    grid_rows: Annotated[int, Form()] = 8,
    grid_cols: Annotated[int, Form()] = 8,
    cell_threshold: Annotated[float, Form()] = 0.10,
) -> ScanDetail:
    # Validate the cheap things first: the type, then the size.
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidImageError("Please upload a JPG or PNG image.")

    limit = settings.max_upload_bytes
    data = file.file.read(limit + 1)  # read one byte too many to detect oversize
    if len(data) > limit:
        raise FileTooLargeError(f"The file is larger than {settings.max_upload_mb} MB.")
    if not data:
        raise InvalidImageError("The uploaded file is empty.")

    # Built here (not as a FastAPI model) so blank form inputs mean "not given"
    # and so every validation failure goes through one error format.
    params = AnalyzeParams(
        mode=mode,
        field_id=field_id,
        field_name=field_name,
        area_ha=area_ha,
        dose_l_per_ha=dose_l_per_ha,
        price_per_l=price_per_l,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        cell_threshold=cell_threshold,
    )

    return service.analyze(data, params)
