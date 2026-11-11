"""All ML models the app has loaded, by key. Built once at startup."""

import logging
from dataclasses import dataclass
from typing import Optional

from app.clients.base import SegmentationClient
from app.clients.factory import build_model_client
from app.core.config import ModelSpec, Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedModel:
    key: str
    label: str
    client: SegmentationClient


class UnknownModelKey(KeyError):
    pass


class ModelRegistry:
    def __init__(self, models: list[LoadedModel], default_key: str):
        if not models:
            raise ValueError("at least one model is required")
        self._models = {m.key: m for m in models}
        if default_key not in self._models:
            raise ValueError(f"default model '{default_key}' is not loaded")
        self.default_key = default_key

    # ------------------------------------------------------------ building

    @classmethod
    def from_settings(cls, settings: Settings) -> "ModelRegistry":
        loaded = []
        for i, spec in enumerate(settings.model_specs()):
            client = build_model_client(spec, settings.hf_token, index=i)
            logger.info("model %s (%s): backend=%s ready=%s", spec.key, spec.label, client.backend, client.is_ready())
            loaded.append(LoadedModel(spec.key, spec.label, client))
        return cls(loaded, settings.default_model_key())

    @classmethod
    def single(cls, client: SegmentationClient, key: str = "default", label: str = "ML segmentation") -> "ModelRegistry":
        """One model (tests, and the classic single-model setup)."""
        return cls([LoadedModel(key, label, client)], key)

    @classmethod
    def of(cls, specs: list[tuple[str, str, SegmentationClient]], default_key: Optional[str] = None) -> "ModelRegistry":
        models = [LoadedModel(k, label, c) for k, label, c in specs]
        return cls(models, default_key or models[0].key)

    # ------------------------------------------------------------ lookups

    @property
    def keys(self) -> list[str]:
        return list(self._models)

    def get(self, key: str) -> LoadedModel:
        try:
            return self._models[key]
        except KeyError:
            raise UnknownModelKey(key) from None

    @property
    def default(self) -> LoadedModel:
        return self._models[self.default_key]

    def label(self, key: Optional[str]) -> Optional[str]:
        """Display name for a stored key; a key no longer configured shows as itself."""
        if not key:
            return None
        model = self._models.get(key)
        return model.label if model else key

    def labels(self) -> dict[str, str]:
        return {k: m.label for k, m in self._models.items()}

    def __iter__(self):
        return iter(self._models.values())
