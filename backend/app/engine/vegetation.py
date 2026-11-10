from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .engine_types import BinaryMask, FloatImage, RGBImage
from .params import DEFAULT_PARAMS, ClassicalParams

# Image format constants
RGB_CHANNELS = 3
RGB_DIM = 3

# HSV vegetation filtering thresholds
HSV_HUE_MIN = 30
HSV_HUE_MAX = 90
HSV_SATURATION_MIN = 30
HSV_VALUE_MIN = 30

# Fixed ExG range for Otsu threshold scaling.
_EXG_LO = -0.5
_EXG_HI = 1.0


def excess_green(rgb: RGBImage) -> FloatImage:
    """
    Calculate Excess Green (ExG) using chromatic coordinates.

    Input:
        RGB image: (H, W, 3), uint8

    Output:
        ExG map: (H, W), float32
    """
    if rgb.ndim != RGB_DIM or rgb.shape[2] != RGB_CHANNELS:
        raise ValueError("Expected RGB image with shape (H, W, 3)")

    image = rgb.astype(np.float32)

    # Normalize RGB channels.
    channel_sum = image.sum(axis=2) + 1e-6

    r = image[..., 0] / channel_sum
    g = image[..., 1] / channel_sum
    b = image[..., 2] / channel_sum

    # Excess Green index.
    exg = 2.0 * g - r - b

    return exg.astype(np.float32)


def vegetation_mask(
    rgb: RGBImage,
    p: ClassicalParams = DEFAULT_PARAMS,
) -> BinaryMask:
    """
    Generate a binary vegetation mask.

    Returns:
        255 = vegetation
        0   = background / soil

    """
    if rgb.dtype != np.uint8:
        raise ValueError("Expected RGB image with dtype uint8")

    if rgb.ndim != RGB_DIM or rgb.shape[2] != RGB_CHANNELS:
        raise ValueError("Expected RGB image with shape (H, W, 3)")

    # 1. Calculate Excess Green.
    exg = excess_green(rgb)

    # 2. Scale ExG to 8-bit range for Otsu thresholding.
    exg_u8 = np.clip(
        (exg - _EXG_LO) / (_EXG_HI - _EXG_LO) * 255.0,
        0,
        255,
    ).astype(np.uint8)

    # 3. Calculate automatic threshold using Otsu.
    otsu_value, _ = cv2.threshold(
        exg_u8,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    # Convert threshold back to original ExG scale.
    otsu_threshold = otsu_value / 255.0 * (_EXG_HI - _EXG_LO) + _EXG_LO

    # Apply minimum threshold floor.
    threshold = max(otsu_threshold, p.min_exg)

    # 4. Identify vegetation pixels.
    vegetation = exg > threshold

    # 5. Optional HSV filtering.
    if p.use_hsv:
        hsv = cast(
            "NDArray[np.uint8]",
            cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV),
        )

        h = hsv[..., 0]
        s = hsv[..., 1]
        v = hsv[..., 2]

        vegetation &= (
            (h >= HSV_HUE_MIN)
            & (h <= HSV_HUE_MAX)
            & (s >= HSV_SATURATION_MIN)
            & (v >= HSV_VALUE_MIN)
        )

    mask: BinaryMask = vegetation.astype(np.uint8) * 255

    # 6. Morphological opening to remove small noise.
    kernel = np.ones(
        (p.open_kernel, p.open_kernel),
        dtype=np.uint8,
    )

    mask = cast(
        "BinaryMask",
        cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
        ),
    )

    # 7. Remove tiny connected components.
    min_pixels = max(
        8,
        int(p.min_area_frac * mask.size),
    )

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8),
        connectivity=8,
    )

    labels = cast("NDArray[np.int32]", labels)

    # Background is label 0.
    keep = np.zeros(num_labels, dtype=bool)

    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_pixels

    cleaned_mask: BinaryMask = keep[labels].astype(np.uint8) * 255

    return cleaned_mask
