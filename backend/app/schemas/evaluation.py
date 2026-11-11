from typing import Any, Optional

from pydantic import BaseModel


class EvaluationEntry(BaseModel):
    """One method or model scored on one test set."""

    variant: str  # "classical" or "ml-<key>"
    method: str  # classical | ml
    model_key: Optional[str] = None
    label: str  # "Classical" or the model's display name
    dataset: str  # name of the test set, e.g. "CWFID shared test set (20 images)"
    metrics: dict[str, Any]  # what scripts/evaluate.py wrote


class ModelRef(BaseModel):
    key: str
    label: str


class EvaluationResponse(BaseModel):
    """`entries` holds every stored result. The older single-model fields stay
    for compatibility and are null until their file exists."""

    entries: list[EvaluationEntry] = []
    models: list[ModelRef] = []  # every configured model, evaluated or not
    training_reports: dict[str, dict[str, Any]] = {}  # model key -> report from the ML team

    classical: Optional[dict[str, Any]] = None
    ml: Optional[dict[str, Any]] = None
    ml_training_report: Optional[dict[str, Any]] = None
