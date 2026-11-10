"""
The heart of the backend: photo in -> stored scan with one result per method.

Rules this module guarantees:
* A bad upload is rejected before anything is written.
* If anything fails after files were written, those files are deleted.
* A failing method never hides a working one in Compare mode.
* The ML model being unavailable never crashes the request.
"""

import io
import logging
import time
import uuid
from typing import Optional

import numpy as np
from PIL import Image, ImageOps
from sqlalchemy.exc import IntegrityError

from app.clients.base import SegmentationClient, StorageClient
from app.core.config import Settings
from app.core.enums import Method, Mode, ResultStatus
from app.core.exceptions import (
    InvalidImageError,
    ModelUnavailableError,
    NotFoundError,
)
from app.engine import (
    CROP,
    SOIL,
    WEED,
    analyze_grid,
    classical_segment_with_info,
    compute_savings,
    encode_jpeg,
    pressure_level,
    render_overlay,
    resize_to_width,
)
from app.models import Field, Scan, ScanResult
from app.repositories.field_repository import FieldRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.analysis import AnalyzeParams
from app.schemas.scan import ScanDetail
from app.services.mappers import to_scan_detail

logger = logging.getLogger(__name__)

MAX_PIXELS = 50_000_000  # decompression-bomb guard, checked before decoding
ALLOWED_FORMATS = {"JPEG", "PNG"}
INVALID_IMAGE_MESSAGE = "The file is not a valid JPG or PNG image."


class AnalysisService:
    def __init__(
        self,
        scans: ScanRepository,
        fields: FieldRepository,
        storage: StorageClient,
        segmenter: SegmentationClient,
        settings: Settings,
    ):
        self.scans = scans
        self.fields = fields
        self.storage = storage
        self.segmenter = segmenter
        self.settings = settings

    # ------------------------------------------------------------------ public

    def analyze(self, data: bytes, params: AnalyzeParams) -> ScanDetail:
        started = time.perf_counter()
        rgb = self._decode(data)
        height, width = rgb.shape[:2]
        mode = Mode(params.mode)

        # Fail fast, before touching the disk: ML-only with no model.
        if mode is Mode.ML and not self.segmenter.is_ready():
            raise ModelUnavailableError(self._unavailable_message())

        field = self._resolve_field(params)

        base_key = f"scans/{uuid.uuid4().hex}"
        saved_keys: list[str] = []
        try:
            original_key = self.storage.save(f"{base_key}/original.jpg", encode_jpeg(rgb))
            saved_keys.append(original_key)

            results = [
                self._run_method(method, rgb, params, base_key, saved_keys)
                for method in self._methods_for(mode)
            ]

            scan = Scan(
                field_id=field.id if field else None,
                mode=mode.value,
                original_key=original_key,
                width=width,
                height=height,
                area_ha=params.area_ha,
                dose_l_per_ha=params.dose_l_per_ha,
                price_per_l=params.price_per_l,
                grid_rows=params.grid_rows,
                grid_cols=params.grid_cols,
                cell_threshold=params.cell_threshold,
                results=results,
            )
            scan = self.scans.add(scan)
        except Exception:
            self._cleanup(saved_keys)
            raise

        logger.info(
            "analysis done scan_id=%s mode=%s statuses=%s total_ms=%d",
            scan.id,
            mode.value,
            {r.method: r.status for r in results},
            (time.perf_counter() - started) * 1000,
        )
        return to_scan_detail(scan, self.storage)

    # ------------------------------------------------------------------ decode

    def _decode(self, data: bytes) -> np.ndarray:
        """Bytes -> RGB uint8 array, decoded the same way as scripts/common.load_rgb
        so API results match the evaluation numbers."""
        try:
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise InvalidImageError(INVALID_IMAGE_MESSAGE)
                if probe.width * probe.height > MAX_PIXELS:
                    raise InvalidImageError("The image is too large (more than 50 megapixels).")
                probe.verify()

            # verify() invalidates the object, so open again for real decoding.
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        except InvalidImageError:
            raise
        except Exception as exc:
            raise InvalidImageError(INVALID_IMAGE_MESSAGE) from exc

        if rgb.ndim != 3 or rgb.shape[0] < 2 or rgb.shape[1] < 2:
            raise InvalidImageError(INVALID_IMAGE_MESSAGE)
        return resize_to_width(rgb, self.settings.working_width)

    # ------------------------------------------------------------------ fields

    def _resolve_field(self, params: AnalyzeParams) -> Optional[Field]:
        if params.field_id is not None:  # field_id wins if both were sent
            field = self.fields.get(params.field_id)
            if field is None:
                raise NotFoundError(f"Field {params.field_id} does not exist.")
            return field

        if params.field_name:
            existing = self.fields.get_by_name(params.field_name)
            if existing:
                return existing
            try:
                return self.fields.create(params.field_name)
            except IntegrityError:  # another request created it a moment ago
                return self.fields.get_by_name(params.field_name)
        return None

    # ----------------------------------------------------------------- methods

    @staticmethod
    def _methods_for(mode: Mode) -> list[Method]:
        if mode is Mode.CLASSICAL:
            return [Method.CLASSICAL]
        if mode is Mode.ML:
            return [Method.ML]
        return [Method.CLASSICAL, Method.ML]

    def _unavailable_message(self) -> str:
        detail = self.segmenter.detail
        return "The ML model is not available." + (f" Reason: {detail}" if detail else "")

    def _run_method(
        self,
        method: Method,
        rgb: np.ndarray,
        params: AnalyzeParams,
        base_key: str,
        saved_keys: list[str],
    ) -> ScanResult:
        is_ml = method is Method.ML
        model_id = self.segmenter.model_id if is_ml else None
        compare = params.mode == Mode.COMPARE.value

        started = time.perf_counter()

        def not_ok(status: ResultStatus, detail: Optional[str]) -> ScanResult:
            return ScanResult(
                method=method.value,
                status=status.value,
                status_detail=detail,
                model_id=model_id,
                processing_ms=int((time.perf_counter() - started) * 1000),
            )

        status_detail: Optional[str] = None
        mask: Optional[np.ndarray] = None

        try:
            if is_ml:
                if not self.segmenter.is_ready():
                    if not compare:
                        raise ModelUnavailableError(self._unavailable_message())
                    return not_ok(ResultStatus.MODEL_UNAVAILABLE, self.segmenter.detail)
                mask = self._validated_ml_mask(self.segmenter.predict(rgb), rgb)
            else:
                mask, info = classical_segment_with_info(rgb)
                if mask is None:
                    status_detail = str(info.get("reason", "rows_not_detected"))
                    return not_ok(ResultStatus.ROWS_NOT_DETECTED, status_detail)

            grid = analyze_grid(mask, params.grid_rows, params.grid_cols, params.cell_threshold)
            savings = compute_savings(
                params.area_ha,
                params.dose_l_per_ha,
                params.price_per_l,
                grid.spray_fraction,
            )
            pressure = pressure_level(
                grid.weed_pct,
                self.settings.pressure_low_max,
                self.settings.pressure_high_min,
            )
            processing_ms = int((time.perf_counter() - started) * 1000)
        except ModelUnavailableError as exc:
            if is_ml and compare:
                return not_ok(ResultStatus.MODEL_UNAVAILABLE, exc.message)
            raise
        except _InvalidModelOutput as exc:
            logger.error("ML model returned invalid output: %s", exc)
            return not_ok(ResultStatus.FAILED, "invalid_model_output")
        except Exception:
            if is_ml and compare:
                logger.exception("ML inference failed")
                return not_ok(ResultStatus.FAILED, "inference_error")
            raise

        overlay_key = self.storage.save(
            f"{base_key}/{method.value}_overlay.png",
            render_overlay(rgb, mask),
        )
        saved_keys.append(overlay_key)
        mask_key = self.storage.save(f"{base_key}/{method.value}_mask.png", _encode_mask(mask))
        saved_keys.append(mask_key)

        return ScanResult(
            method=method.value,
            status=ResultStatus.OK.value,
            status_detail=None,
            model_id=model_id,
            vegetation_pct=grid.vegetation_pct,
            crop_pct=grid.crop_pct,
            weed_pct=grid.weed_pct,
            pressure=pressure,
            overlay_key=overlay_key,
            mask_key=mask_key,
            grid=grid.density,
            spray_cells=grid.spray_cells,
            blanket_cost=savings["blanket_cost"],
            spot_cost=savings["spot_cost"],
            saved_litres=savings["saved_litres"],
            saved_pct=savings["saved_pct"],
            processing_ms=processing_ms,
        )

    @staticmethod
    def _validated_ml_mask(mask: object, rgb: np.ndarray) -> np.ndarray:
        """Never trust model output: wrong shape or values would corrupt stats."""
        if not isinstance(mask, np.ndarray) or mask.ndim != 2:
            raise _InvalidModelOutput("mask is not a 2-D array")
        if mask.shape != rgb.shape[:2]:
            raise _InvalidModelOutput(f"mask shape {mask.shape} != image {rgb.shape[:2]}")
        if mask.dtype != np.uint8:
            raise _InvalidModelOutput(f"mask dtype {mask.dtype} != uint8")
        if not np.isin(mask, (SOIL, CROP, WEED)).all():
            raise _InvalidModelOutput("mask contains values other than 0, 1, 2")
        return mask

    # ----------------------------------------------------------------- cleanup

    def _cleanup(self, keys: list[str]) -> None:
        for key in keys:
            try:
                self.storage.delete(key)
            except Exception:
                logger.warning("could not delete %s during cleanup", key, exc_info=True)


class _InvalidModelOutput(Exception):
    pass


def _encode_mask(mask: np.ndarray) -> bytes:
    """Greyscale PNG with the raw class ids (0, 1, 2). Lossless, a few KB."""
    buffer = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8), mode="L").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
