from typing import Literal, Optional

from pydantic import BaseModel


class ModelStatus(BaseModel):
    backend: str  # fake | unavailable | hf
    model_id: str
    ready: bool
    detail: Optional[str] = None  # why the model is not ready


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]  # degraded = the database is not reachable
    database: Literal["ok", "error"]
    model: ModelStatus
