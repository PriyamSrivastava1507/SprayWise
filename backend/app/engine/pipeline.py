"""Full classical segmentation pipeline: vegetation -> crop rows -> crop/weed."""

from typing import TypedDict

import numpy as np

from .engine_types import LabelMask, RGBImage
from .params import DEFAULT_PARAMS, ClassicalParams
from .rows import estimate_rows, split_crop_weed
from .vegetation import vegetation_mask


class _RequiredInfo(TypedDict):
    vegetation_px: int
    rows_detected: bool


class SegmentationInfo(_RequiredInfo, total=False):
    """
    Diagnostics returned next to the mask (useful for tuning and logging).

    Always present:
        vegetation_px: number of pixels flagged as vegetation
        rows_detected: whether crop rows were found

    Present when rows were found:
        angle_deg, n_rows, spacing_px, periodicity

    Present when rows were NOT found:
        reason: why the search was rejected (for example "weak_periodicity")
        periodicity: the value that fell short, when that was the reason
    """

    angle_deg: float
    n_rows: int
    spacing_px: float
    periodicity: float
    reason: str


def classical_segment_with_info(
    rgb: RGBImage,
    p: ClassicalParams = DEFAULT_PARAMS,
) -> tuple[LabelMask | None, SegmentationInfo]:
    """
    Run the full classical pipeline and return diagnostics as well.

    Input:
        RGB image: (H, W, 3), uint8

    Output:
        mask: (H, W) uint8 with 0 soil, 1 crop, 2 weed, or None when crop
            rows were not detected (the caller reports "rows_not_detected")
        info: diagnostics, see SegmentationInfo
    """
    veg = vegetation_mask(rgb, p)

    info: SegmentationInfo = {
        "vegetation_px": int(np.count_nonzero(veg)),
        "rows_detected": False,
    }

    rejection: dict[str, object] = {}
    model = estimate_rows(veg, p, diag=rejection)

    if model is None:
        reason = rejection.get("reason")
        if isinstance(reason, str):
            info["reason"] = reason

        periodicity = rejection.get("periodicity")
        if isinstance(periodicity, float):
            info["periodicity"] = periodicity

        return None, info

    info["rows_detected"] = True
    info["angle_deg"] = model.angle_deg
    info["n_rows"] = len(model.centers)
    info["spacing_px"] = model.spacing
    info["periodicity"] = model.periodicity

    return split_crop_weed(veg, model, p), info


def classical_segment(
    rgb: RGBImage,
    p: ClassicalParams = DEFAULT_PARAMS,
) -> LabelMask | None:
    """
    Segment a field photo into soil, crop and weed using crop-row geometry.

    This is the function the analysis service calls.

    Returns:
        (H, W) uint8 mask with 0 soil, 1 crop, 2 weed, or None when crop
        rows were not detected

    """
    return classical_segment_with_info(rgb, p)[0]
