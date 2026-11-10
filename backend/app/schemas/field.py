"""Shapes for fields and their trend."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class FieldOut(BaseModel):
    id: int
    name: str
    created_at: datetime


class TrendPoint(BaseModel):
    scan_id: int
    created_at: datetime
    weed_pct: Optional[float] = None
    saved_pct: Optional[float] = None


class TrendResponse(BaseModel):
    field: FieldOut
    method: Literal["classical", "ml"]
    points: list[TrendPoint]  # oldest first, successful results only
