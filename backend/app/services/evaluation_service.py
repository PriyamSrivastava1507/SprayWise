"""Serve the metrics written offline by scripts/evaluate.py."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.schemas.evaluation import EvaluationResponse

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def get(self) -> EvaluationResponse:
        return EvaluationResponse(
            classical=self._read("classical.json"),
            ml=self._read("ml.json"),
            ml_training_report=self._read("ml_training_report.json"),
        )

    def _read(self, name: str) -> Optional[dict[str, Any]]:
        path = self.directory / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            logger.warning("could not read evaluation file %s", path, exc_info=True)
            return None
        return data if isinstance(data, dict) else None
