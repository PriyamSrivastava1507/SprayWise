"""
Recalculate a stored scan with other settings (zones, threshold, area, dose,
price) without running segmentation again: the saved label masks are re-cut
into zones. With save=False nothing is written, so the UI can preview changes
while a slider moves; with save=True the scan's settings and results are updated.
"""

import io
import logging
from collections.abc import Mapping

import numpy as np
from PIL import Image

from app.clients.base import StorageClient
from app.core.config import Settings
from app.core.enums import ResultStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.engine import analyze_grid, compute_savings, pressure_level
from app.repositories.scan_repository import ScanRepository
from app.schemas.analysis import ScanSettings
from app.schemas.scan import ScanDetail
from app.services.mappers import to_scan_detail

logger = logging.getLogger(__name__)


class RecalculationService:
    def __init__(self, scans: ScanRepository, storage: StorageClient, settings: Settings, labels: Mapping[str, str] = {}):
        self.scans = scans
        self.storage = storage
        self.settings = settings
        self.labels = labels

    def recalculate(self, scan_id: int, new: ScanSettings, save: bool) -> ScanDetail:
        scan = self.scans.get(scan_id)
        if scan is None:
            raise NotFoundError(f"Scan {scan_id} does not exist.")

        usable = [r for r in scan.results if r.status == ResultStatus.OK.value and r.mask_key]
        if not usable:
            raise ConflictError(
                "This scan cannot be recalculated: it has no successful result with a saved mask."
            )
        masks = {r.id: self._read_mask(r.mask_key) for r in usable}

        try:
            for field, value in new.model_dump().items():
                setattr(scan, field, value)
            for result in usable:
                grid = analyze_grid(masks[result.id], new.grid_rows, new.grid_cols, new.cell_threshold)
                savings = compute_savings(new.area_ha, new.dose_l_per_ha, new.price_per_l, grid.spray_fraction)
                result.grid = grid.density
                result.spray_cells = grid.spray_cells
                result.vegetation_pct = grid.vegetation_pct
                result.crop_pct = grid.crop_pct
                result.weed_pct = grid.weed_pct
                result.pressure = pressure_level(
                    grid.weed_pct, self.settings.pressure_low_max, self.settings.pressure_high_min
                )
                result.blanket_cost = savings["blanket_cost"]
                result.spot_cost = savings["spot_cost"]
                result.saved_litres = savings["saved_litres"]
                result.saved_pct = savings["saved_pct"]

            detail = to_scan_detail(scan, self.storage, self.labels)
            if save:
                self.scans.commit()
                logger.info("scan %s recalculated and saved", scan_id)
            else:
                self.scans.discard()
            return detail
        except Exception:
            self.scans.discard()
            raise

    def _read_mask(self, key: str) -> np.ndarray:
        try:
            with Image.open(io.BytesIO(self.storage.read(key))) as image:
                return np.asarray(image.convert("L"), dtype=np.uint8)
        except Exception as exc:
            raise ConflictError("A saved mask for this scan could not be read.") from exc
