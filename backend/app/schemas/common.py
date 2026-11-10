"""Shapes shared by every endpoint."""

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Every error the API returns has exactly this shape."""

    error: ErrorBody


from typing import Generic, TypeVar  # noqa: E402

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Every list endpoint returns this envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int
