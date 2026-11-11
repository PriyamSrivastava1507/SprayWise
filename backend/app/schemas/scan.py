"""Response shapes for scans. This is the contract the frontend codes against:
field names are snake_case, percentages are 0..100, grid densities are
fractions 0..1, and times are UTC ISO 8601."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FieldRef(BaseModel):
    id: int
    name: str


class ScanParams(BaseModel):
    area_ha: float
    dose_l_per_ha: float
    price_per_l: float
    grid_rows: int
    grid_cols: int
    cell_threshold: float


class Savings(BaseModel):
    """Spot spraying versus spraying the whole field. All values are null when
    the result is not ok. Litres and money are rounded to 2 decimals."""

    blanket_litres: Optional[float] = None  # area x dose
    spot_litres: Optional[float] = None
    saved_litres: Optional[float] = None
    blanket_cost: Optional[float] = None
    spot_cost: Optional[float] = None
    saved_cost: Optional[float] = None
    saved_pct: Optional[float] = None


class ScanResultOut(BaseModel):
    """
    One method's outcome. Every result has this same shape: when ``status`` is
    not "ok" the statistics are null, so the frontend only has to look at
    ``status`` (and ``status_detail`` for the reason).
    """

    method: str  # classical | ml
    model_key: Optional[str] = None  # which ML model, e.g. "cwfid"; null for classical
    model_label: Optional[str] = None  # its display name, e.g. "ML (CWFID)"
    status: str  # ok | rows_not_detected | model_unavailable | failed
    status_detail: Optional[str] = None  # e.g. "weak_periodicity"
    model_id: Optional[str] = None  # ml only; "fake-demo-model" means a demo result

    vegetation_pct: Optional[float] = None
    crop_pct: Optional[float] = None
    weed_pct: Optional[float] = None
    pressure: Optional[str] = None  # Low | Medium | High

    overlay_url: Optional[str] = None  # photo with crop green and weeds red
    mask_url: Optional[str] = None  # greyscale PNG, pixel value = class (0 soil, 1 crop, 2 weed)
    grid: Optional[list[list[float]]] = None  # weed density per cell, 0..1
    spray_cells: Optional[list[list[int]]] = None  # [row, col] of cells to spray

    savings: Savings
    processing_ms: Optional[int] = None


class ScanDetail(BaseModel):
    id: int
    field: Optional[FieldRef] = None
    created_at: datetime
    mode: str  # classical | ml | compare
    width: int
    height: int
    original_url: str
    params: ScanParams
    results: list[ScanResultOut]
