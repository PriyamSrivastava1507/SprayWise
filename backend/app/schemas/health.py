from typing import Literal, Optional

from pydantic import BaseModel


class ModelStatus(BaseModel):
    backend: str  # fake | unavailable | hf
    model_id: str
    ready: bool
    detail: Optional[str] = None  # why the model is not ready


class PressureThresholds(BaseModel):
    """Weed % limits: Low below low_max, High from high_min, Medium between."""

    low_max: float
    high_min: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]  # degraded = the database is not reachable
    database: Literal["ok", "error"]
    model: ModelStatus
    pressure_thresholds: PressureThresholds
