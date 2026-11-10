"""Fields and the weed trend of one field."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import FieldServiceDep
from app.schemas.common import ErrorResponse
from app.schemas.field import FieldCreate, FieldOut, TrendResponse

router = APIRouter(prefix="/fields", tags=["fields"])
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Field not found"}}


@router.get("", response_model=list[FieldOut], summary="List fields, by name")
def list_fields(service: FieldServiceDep) -> list[FieldOut]:
    return service.list()


@router.post(
    "",
    response_model=FieldOut,
    status_code=201,
    responses={409: {"model": ErrorResponse, "description": "Name already exists"}},
)
def create_field(body: FieldCreate, service: FieldServiceDep) -> FieldOut:
    return service.create(body.name)


@router.get("/{field_id}", response_model=FieldOut, responses=NOT_FOUND)
def get_field(field_id: int, service: FieldServiceDep) -> FieldOut:
    return service.get(field_id)


@router.get("/{field_id}/trend", response_model=TrendResponse, responses=NOT_FOUND)
def field_trend(
    field_id: int,
    service: FieldServiceDep,
    method: Annotated[Literal["classical", "ml"], Query()] = "classical",
) -> TrendResponse:
    return service.trend(field_id, method)
