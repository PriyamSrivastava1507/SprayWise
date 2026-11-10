"""Weed-density grid, spray cells and coverage statistics."""

from dataclasses import dataclass

import numpy as np

from .constants import CROP, WEED
from .engine_types import LabelMask


@dataclass
class GridResult:
    """Grid analysis of a label mask."""

    density: list[list[float]]  # weed fraction (0..1) per cell
    spray_cells: list[list[int]]  # [row, col] of cells above the threshold
    spray_fraction: float  # spray cells / all cells (0..1)
    vegetation_pct: float  # percentages of ALL pixels (0..100)
    crop_pct: float
    weed_pct: float


def analyze_grid(
    mask: LabelMask,
    rows: int,
    cols: int,
    threshold: float,
) -> GridResult:
    """
    Cut the mask into ``rows`` x ``cols`` cells and measure weed density.

    Cell edges are integers from ``np.linspace`` so images whose size does
    not divide evenly still work. ``threshold`` is a fraction (0..1);
    the returned ``*_pct`` fields are percentages (0..100).
    """
    height, width = mask.shape
    rows = min(rows, height)
    cols = min(cols, width)

    row_edges = np.linspace(0, height, rows + 1).astype(np.intp)
    col_edges = np.linspace(0, width, cols + 1).astype(np.intp)

    weed = (mask == WEED).astype(np.int64)

    sums = np.add.reduceat(
        np.add.reduceat(weed, row_edges[:-1], axis=0),
        col_edges[:-1],
        axis=1,
    )
    areas = np.outer(np.diff(row_edges), np.diff(col_edges)).astype(np.float64)
    density = sums / areas

    spray = np.argwhere(density > threshold)

    total = float(mask.size)
    crop_pct = 100.0 * float(np.count_nonzero(mask == CROP)) / total
    weed_pct = 100.0 * float(weed.sum()) / total

    return GridResult(
        density=np.round(density, 4).tolist(),
        spray_cells=spray.tolist(),
        spray_fraction=len(spray) / float(rows * cols),
        vegetation_pct=round(crop_pct + weed_pct, 2),
        crop_pct=round(crop_pct, 2),
        weed_pct=round(weed_pct, 2),
    )
