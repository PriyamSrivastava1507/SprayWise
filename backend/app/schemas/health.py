from typing import Literal, Optional

from pydantic import BaseModel


class ModelStatus(BaseModel):
    backend: str  # fake | unavailable | hf
    model_id: str
    ready: bool
    detail: Optional[str] = None  # why the model is not ready


class ModelInfo(ModelStatus):
    """One configured ML model (GET /models and the `models` list in /health)."""

    key: str  # used in requests: models=cwfid,we3ds
    label: str  # shown to people
    default: bool


class PressureThresholds(BaseModel):
    """Weed % limits: Low below low_max, High from high_min, Medium between."""

    low_max: float
    high_min: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]  # degraded = the database is not reachable
    database: Literal["ok", "error"]
    model: ModelStatus  # the default model (kept for older clients)
    models: list[ModelInfo]  # every configured model
    pressure_thresholds: PressureThresholds
