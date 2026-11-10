"""Colour overlay of a label mask on the original photo."""

import io

import numpy as np
from PIL import Image

from .constants import CROP, WEED
from .engine_types import LabelMask, RGBImage

CROP_COLOR = (34, 197, 94)  # green
WEED_COLOR = (239, 68, 68)  # red


def render_overlay(
    rgb: RGBImage,
    mask: LabelMask,
    alpha: float = 0.55,
) -> bytes:
    """Blend crop (green) and weed (red) over the photo and return PNG bytes."""
    out = rgb.astype(np.float32)

    for class_id, color in ((CROP, CROP_COLOR), (WEED, WEED_COLOR)):
        selected = mask == class_id
        out[selected] = (1 - alpha) * out[selected] + alpha * np.array(
            color,
            dtype=np.float32,
        )

    buffer = io.BytesIO()
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()
