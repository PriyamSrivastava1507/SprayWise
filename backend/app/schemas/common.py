"""Shapes shared by every endpoint."""

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Every error the API returns has exactly this shape."""

    error: ErrorBody
