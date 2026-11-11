from typing import Optional

import numpy as np

from app.engine.constants import CROP, SOIL, WEED
from app.engine.vegetation import vegetation_mask


class FakeSegmentationClient:
    """Stand-in segmentation client for local development and UI testing."""

    backend: str = "fake"
    model_id: str = "fake-demo-model"
    detail: Optional[str] = None

    def __init__(self, weed_side: str = "right") -> None:
        # Which half of the vegetation is called weed. Two fake models with
        # different sides make model comparisons visible during UI work.
        self.weed_side = weed_side

    def is_ready(self) -> bool:
        return True

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        veg = vegetation_mask(rgb) > 0
        out = np.full(veg.shape, SOIL, dtype=np.uint8)
        out[veg] = CROP

        half = veg.shape[1] // 2
        # Mark one half of detected vegetation as weed
        side = slice(half, None) if self.weed_side == "right" else slice(0, half)
        out[:, side][veg[:, side]] = WEED

        return out

