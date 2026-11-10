from typing import Any, Optional

from pydantic import BaseModel


class EvaluationResponse(BaseModel):
    """Each part is null until its file exists ("Not evaluated yet" in the UI)."""

    classical: Optional[dict[str, Any]] = None
    ml: Optional[dict[str, Any]] = None
    ml_training_report: Optional[dict[str, Any]] = None
