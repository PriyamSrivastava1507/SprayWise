from typing import Optional, Protocol

import numpy as np


class SegmentationClient(Protocol):
    backend: str  # "fake" | "unavailable" | "hf"
    model_id: str
    detail: Optional[str]  # why the model is not ready, otherwise None

    def is_ready(self) -> bool:
        """Check whether the model is loaded and ready for inference."""
        ...

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        """Run segmentation on an RGB image.

        Args:
            rgb: uint8 array of shape (H, W, 3).

        Returns:
            uint8 array of shape (H, W) with class values 0 (soil), 1 (crop), 2 (weed).
        """
        ...


class StorageClient(Protocol):
    def save(self, key: str, data: bytes) -> str:
        """Save raw bytes under the given relative key.

        Returns:
            The key under which the data was saved.
        """
        ...

    def read(self, key: str) -> bytes:
        """Read bytes stored under the given key."""
        ...

    def url(self, key: str) -> str:
        """Return the public URL path for the key."""
        ...

    def delete(self, key: str) -> None:
        """Delete file at key if it exists."""
        ...

