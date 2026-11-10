import logging
from typing import Optional

import numpy as np

from app.clients.base import SegmentationClient, StorageClient
from app.clients.segmentation_fake import FakeSegmentationClient
from app.clients.segmentation_hf import HFSegformerClient
from app.clients.storage_local import LocalStorageClient
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError

logger = logging.getLogger(__name__)


class UnavailableSegmentationClient:
    """Fallback client when the ML model cannot be loaded or is offline."""

    def __init__(self, model_id: str = "unavailable") -> None:
        self.model_id = model_id

    def is_ready(self) -> bool:
        return False

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        raise ModelUnavailableError(
            f"The ML model '{self.model_id}' is not loaded or is offline"
        )


def build_segmentation_client(settings: Settings) -> SegmentationClient:
    """Factory creating the appropriate segmentation client based on application settings."""
    if settings.segmentation_backend == "hf":
        try:
            return HFSegformerClient(
                model_id=settings.hf_model_id,
                token=settings.hf_token,
            )
        except Exception:
            logger.exception("Could not load model %s", settings.hf_model_id)
            return UnavailableSegmentationClient(model_id=settings.hf_model_id)

    if settings.segmentation_backend == "unavailable":
        return UnavailableSegmentationClient(model_id=settings.hf_model_id)

    return FakeSegmentationClient()


def build_storage_client(settings: Settings) -> StorageClient:
    """Factory creating the storage client."""
    return LocalStorageClient(root=settings.storage_dir)

