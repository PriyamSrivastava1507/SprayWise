import logging
from typing import Optional

import numpy as np

from app.clients.base import SegmentationClient, StorageClient
from app.clients.segmentation_fake import FakeSegmentationClient
from app.clients.segmentation_hf import HFSegformerClient
from app.clients.storage_local import LocalStorageClient
from app.core.config import ModelSpec, Settings
from app.core.exceptions import ModelUnavailableError

logger = logging.getLogger(__name__)

_MAX_DETAIL_CHARS = 200  # /health is public: keep load errors short


class UnavailableSegmentationClient:
    """Fallback client when the ML model cannot be loaded or is offline."""

    backend: str = "unavailable"

    def __init__(self, model_id: str = "unavailable", detail: Optional[str] = None) -> None:
        self.model_id = model_id
        # Always a readable reason, so /health and the UI can say why ML is off.
        self.detail: Optional[str] = (
            detail or f"The ML model '{model_id}' is not loaded or is offline"
        )

    def is_ready(self) -> bool:
        return False

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        raise ModelUnavailableError(self.detail or "The ML model is not loaded")


def build_model_client(spec: ModelSpec, token: Optional[str] = None, index: int = 0) -> SegmentationClient:
    """Create the client for one model. A model that cannot load becomes
    "unavailable" with the reason, so the app and other models keep working."""
    if spec.backend == "hf":
        try:
            return HFSegformerClient(model_id=spec.path, token=token)
        except Exception as exc:
            logger.exception("Could not load model %s (%s)", spec.key, spec.path)
            reason = f"{type(exc).__name__}: {exc}"[:_MAX_DETAIL_CHARS]
            return UnavailableSegmentationClient(
                model_id=spec.path,
                detail=f"Could not load the ML model ({reason})",
            )
    if spec.backend == "unavailable":
        return UnavailableSegmentationClient(
            model_id=spec.path or spec.key,
            detail=f"The model '{spec.label}' is switched off (backend=unavailable)",
        )
    return FakeSegmentationClient(weed_side="right" if index % 2 == 0 else "left")


def build_segmentation_client(settings: Settings) -> SegmentationClient:
    """
    Create the segmentation client chosen by SEGMENTATION_BACKEND.

    fake        -> artificial demo mask (default while the real model is built)
    unavailable -> ML requests report model_unavailable
    hf          -> the real model; if it fails to load, fall back to
                   "unavailable" so the app still starts and classical mode works
    """
    if settings.segmentation_backend == "hf":
        try:
            return HFSegformerClient(
                model_id=settings.hf_model_id,
                token=settings.hf_token,
            )
        except Exception as exc:
            logger.exception("Could not load model %s", settings.hf_model_id)
            reason = f"{type(exc).__name__}: {exc}"[:_MAX_DETAIL_CHARS]
            return UnavailableSegmentationClient(
                model_id=settings.hf_model_id,
                detail=f"Could not load the ML model ({reason})",
            )

    if settings.segmentation_backend == "unavailable":
        return UnavailableSegmentationClient(
            model_id=settings.hf_model_id,
            detail="ML mode is switched off (SEGMENTATION_BACKEND=unavailable)",
        )

    return FakeSegmentationClient()


def build_storage_client(settings: Settings) -> StorageClient:
    """Create the storage client."""
    return LocalStorageClient(root=settings.storage_dir)
