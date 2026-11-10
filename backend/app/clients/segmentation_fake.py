import numpy as np

from app.engine.constants import CROP, SOIL, WEED
from app.engine.vegetation import vegetation_mask


class FakeSegmentationClient:
    """Stand-in segmentation client for local development and UI testing."""

    model_id: str = "fake-demo-model"

    def is_ready(self) -> bool:
        return True

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        veg = vegetation_mask(rgb) > 0
        out = np.full(veg.shape, SOIL, dtype=np.uint8)
        out[veg] = CROP

        half = veg.shape[1] // 2
        # Mark right half of detected vegetation as weed
        right_veg = veg[:, half:]
        out[:, half:][right_veg] = WEED

        return out

