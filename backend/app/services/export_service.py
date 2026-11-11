"""CSV and PDF reports for one scan result."""

import csv
import io
import logging
from collections.abc import Mapping
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.clients.base import StorageClient
from app.core.enums import ResultStatus
from app.core.exceptions import NotFoundError
from app.models import Scan, ScanResult
from app.repositories.scan_repository import ScanRepository

logger = logging.getLogger(__name__)

DEMO_MODEL_ID = "fake-demo-model"
LIMITATIONS = (
    "Estimates come from a single photo. Weed pressure levels and the savings figure are "
    "decision-support values based on the parameters above (cost is assumed to scale with "
    "the sprayed share of the field); they are not agronomic recommendations. Check results "
    "against the field before spraying."
)


class ExportService:
    def __init__(self, scans: ScanRepository, storage: StorageClient, labels: Mapping[str, str] = {}):
        self.scans = scans
        self.storage = storage
        self.labels = labels

    # ------------------------------------------------------------------ public

    def csv(self, scan_id: int, method: Optional[str], model: Optional[str] = None) -> tuple[str, bytes]:
        scan, result = self._pick(scan_id, method, model)
        spray = {(r, c) for r, c in (result.spray_cells or [])}
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["row", "col", "weed_density", "spray"])
        for r, line in enumerate(result.grid or []):
            for c, density in enumerate(line):
                writer.writerow([r, c, round(density, 4), int((r, c) in spray)])
        return f"scan_{scan.id}_{_variant(result)}.csv", buffer.getvalue().encode("utf-8")

    def pdf(self, scan_id: int, method: Optional[str], model: Optional[str] = None) -> tuple[str, bytes]:
        scan, result = self._pick(scan_id, method, model)
        return f"scan_{scan.id}_{_variant(result)}.pdf", self._build_pdf(scan, result)

    # ----------------------------------------------------------------- helpers

    def _pick(self, scan_id: int, method: Optional[str], model: Optional[str] = None) -> tuple[Scan, ScanResult]:
        scan = self.scans.get(scan_id)
        if scan is None:
            raise NotFoundError(f"Scan {scan_id} does not exist.")
        ok = [r for r in scan.results if r.status == ResultStatus.OK.value]
        chosen = next(
            (
                r for r in ok
                if (method is None or r.method == method) and (model is None or r.model_key == model)
            ),
            None,
        )
        if chosen is None:
            raise NotFoundError("No successful result for that method or model.")
        return scan, chosen

    def _image(self, key: Optional[str], max_w: float, max_h: float):
        """A picture scaled to fit the box, or None if the file is missing."""
        if not key:
            return None
        try:
            data = self.storage.read(key)
            from PIL import Image as PILImage

            with PILImage.open(io.BytesIO(data)) as im:
                w, h = im.size
            scale = min(max_w / w, max_h / h)
            return Image(io.BytesIO(data), width=w * scale, height=h * scale)
        except Exception:
            logger.warning("could not embed image %s in PDF", key, exc_info=True)
            return None

    def _build_pdf(self, scan: Scan, result: ScanResult) -> bytes:
        styles = getSampleStyleSheet()
        body, small = styles["BodyText"], styles["BodyText"].clone("small", fontSize=8)
        story: list = [
            Paragraph("SprayWise scan report", styles["Title"]),
            Paragraph(
                f"Scan #{scan.id} &middot; {scan.created_at:%Y-%m-%d %H:%M} UTC &middot; "
                f"Field: {escape(scan.field.name) if scan.field else 'not assigned'}",
                body,
            ),
        ]

        if result.method == "classical":
            method_label = "Classical (colour index + crop rows)"
        else:
            name = self.labels.get(result.model_key, result.model_key) if result.model_key else "ML"
            method_label = escape(f"{name}, SegFormer segmentation")
        story.append(Paragraph(f"<b>Method:</b> {method_label}", body))
        if result.model_id:
            story.append(Paragraph(f"<b>Model:</b> {escape(result.model_id)}", body))
        if result.model_id == DEMO_MODEL_ID:
            story.append(
                Paragraph(
                    "<b>Demo result:</b> produced by a placeholder model, not a trained one.",
                    body,
                )
            )
        story.append(Spacer(1, 4 * mm))

        half = (A4[0] - 40 * mm) / 2 - 4 * mm
        pictures = [
            self._image(scan.original_key, half, 52 * mm),
            self._image(result.overlay_key, half, 52 * mm),
        ]
        if all(pictures):
            story.append(Table([pictures, [Paragraph("Original", small), Paragraph("Crop (green) / weed (red)", small)]]))
            story.append(Spacer(1, 4 * mm))

        def table(rows: list[list[str]]) -> Table:
            t = Table(rows, colWidths=[70 * mm, 60 * mm], hAlign="LEFT")
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ]
                )
            )
            return t

        def pct(value: Optional[float]) -> str:
            return "-" if value is None else f"{value:.1f} %"

        story += [
            Paragraph("Parameters", styles["Heading3"]),
            table(
                [
                    ["Parameter", "Value"],
                    ["Area", f"{scan.area_ha:g} ha"],
                    ["Dose", f"{scan.dose_l_per_ha:g} L/ha"],
                    ["Price", f"{scan.price_per_l:g} per L"],
                    ["Grid", f"{scan.grid_rows} x {scan.grid_cols}"],
                    ["Spray cell threshold", f"{scan.cell_threshold * 100:g} % weed"],
                ]
            ),
            Paragraph("Statistics", styles["Heading3"]),
            table(
                [
                    ["Measure", "Value"],
                    ["Vegetation cover", pct(result.vegetation_pct)],
                    ["Crop cover", pct(result.crop_pct)],
                    ["Weed cover", pct(result.weed_pct)],
                    ["Weed pressure", result.pressure or "-"],
                    ["Cells to spray", f"{len(result.spray_cells or [])} of {scan.grid_rows * scan.grid_cols}"],
                ]
            ),
            Paragraph("Savings (spot vs blanket spraying)", styles["Heading3"]),
            table(
                [
                    ["Measure", "Value"],
                    ["Blanket cost", f"{result.blanket_cost:.2f}"],
                    ["Spot cost", f"{result.spot_cost:.2f}"],
                    ["Saved chemical", f"{result.saved_litres:.2f} L"],
                    ["Saved", pct(result.saved_pct)],
                ]
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Limitations.</b> {LIMITATIONS}", small),
            Paragraph(
                "Methods: Excess-Green vegetation index with crop-row geometry (classical); "
                "SegFormer semantic segmentation (ML).",
                small,
            ),
        ]

        buffer = io.BytesIO()
        SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm, title=f"SprayWise scan {scan.id}",
        ).build(story)
        return buffer.getvalue()


def _variant(result: ScanResult) -> str:
    return f"{result.method}-{result.model_key}" if result.model_key else result.method
