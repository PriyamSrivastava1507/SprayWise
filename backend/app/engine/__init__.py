"""Pure computer-vision engine: no FastAPI, database or network code."""

from .constants import CROP, IGNORE, SOIL, WEED
from .grid import GridResult, analyze_grid
from .metrics import confusion_matrix, metrics_from_cm
from .overlay import render_overlay
from .params import DEFAULT_PARAMS, ClassicalParams
from .pipeline import classical_segment, classical_segment_with_info
from .preprocess import encode_jpeg, resize_mask_nearest, resize_to_width
from .rows import RowModel, estimate_rows, split_crop_weed
from .savings import compute_savings, pressure_level
from .vegetation import excess_green, vegetation_mask

__all__ = [
    "CROP",
    "DEFAULT_PARAMS",
    "IGNORE",
    "SOIL",
    "WEED",
    "ClassicalParams",
    "GridResult",
    "RowModel",
    "analyze_grid",
    "classical_segment",
    "classical_segment_with_info",
    "compute_savings",
    "confusion_matrix",
    "encode_jpeg",
    "estimate_rows",
    "excess_green",
    "metrics_from_cm",
    "pressure_level",
    "render_overlay",
    "resize_mask_nearest",
    "resize_to_width",
    "split_crop_weed",
    "vegetation_mask",
]
