"""
Serve the metrics written offline by scripts/evaluate.py.

Files in EVALUATION_DIR:
    <variant>__<dataset>.json   e.g. classical__cwfid-test.json, ml-we3ds__cwfid-test.json
    training_<key>.json         the ML team's training report for one model
Each model's folder may also hold training_report.json; it is used unless
EVALUATION_DIR has a training_<key>.json for the same model.
    classical.json, ml.json, ml_training_report.json   older single-model names
A missing or unreadable file is simply left out ("Not evaluated yet" in the UI).
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.clients.registry import ModelRegistry
from app.schemas.evaluation import EvaluationEntry, EvaluationResponse, ModelRef

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, directory: str, models: Optional[ModelRegistry] = None):
        self.directory = Path(directory)
        self.models = models

    def get(self) -> EvaluationResponse:
        default_key = self.models.default_key if self.models else "default"
        classical, ml = self._read("classical.json"), self._read("ml.json")
        legacy_report = self._read("ml_training_report.json")

        entries: list[EvaluationEntry] = []
        if classical:
            entries.append(self._entry("classical", classical, "classical"))
        if ml:
            entries.append(self._entry(f"ml-{default_key}", ml, "ml"))
        for path in sorted(self.directory.glob("*__*.json")) if self.directory.is_dir() else []:
            data = self._read(path.name)
            if data:
                variant, dataset_slug = path.stem.split("__", 1)
                entries.append(self._entry(variant, data, dataset_slug))

        reports: dict[str, dict[str, Any]] = {}
        for model in self.models or []:
            folder_report = self._read_path(Path(model.path) / "training_report.json") if model.path else None
            if folder_report:
                reports[model.key] = folder_report
        if legacy_report:
            reports[default_key] = legacy_report
        for path in sorted(self.directory.glob("training_*.json")) if self.directory.is_dir() else []:
            data = self._read(path.name)
            if data:
                reports[path.stem[len("training_"):]] = data

        return EvaluationResponse(
            entries=entries,
            models=[ModelRef(key=m.key, label=m.label) for m in self.models] if self.models else [],
            training_reports=reports,
            classical=classical,
            ml=ml,
            ml_training_report=legacy_report,
        )

    def _entry(self, variant: str, data: dict[str, Any], fallback_dataset: str) -> EvaluationEntry:
        if variant == "classical":
            method, key, label = "classical", None, "Classical"
        else:
            method, key = "ml", variant[3:] if variant.startswith("ml-") else variant
            label = self.models.label(key) if self.models else key
        return EvaluationEntry(
            variant=variant,
            method=method,
            model_key=key,
            label=label or variant,
            dataset=str(data.get("dataset") or fallback_dataset),
            metrics=data,
        )

    def _read(self, name: str) -> Optional[dict[str, Any]]:
        return self._read_path(self.directory / name)

    @staticmethod
    def _read_path(path: Path) -> Optional[dict[str, Any]]:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            logger.warning("could not read evaluation file %s", path, exc_info=True)
            return None
        return data if isinstance(data, dict) else None
