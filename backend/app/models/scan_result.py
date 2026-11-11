from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scan import Scan


class ScanResult(Base):
    """
    One row per method run, so a Compare scan has two (or more: one per ML
    model). `model_key` says which ML model; it is "" for classical.

    When status is not "ok" the statistics stay NULL, so the API can return
    every result in the same shape and the frontend only inspects `status`.
    """

    __tablename__ = "scan_results"
    __table_args__ = (
        UniqueConstraint("scan_id", "method", "model_key", name="uq_scan_method_model"),  # pyright: ignore[reportCallIssue]
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"),
        index=True,
    )
    method: Mapped[str]  # Method value: classical | ml
    status: Mapped[str]  # ResultStatus value
    status_detail: Mapped[str | None]  # why it was not ok, e.g. "weak_periodicity"
    model_key: Mapped[str] = mapped_column(default="", server_default="")  # e.g. "cwfid"; "" for classical
    model_id: Mapped[str | None]  # what the model client reports (Hub ID or folder)

    vegetation_pct: Mapped[float | None]  # percentages: 0..100
    crop_pct: Mapped[float | None]
    weed_pct: Mapped[float | None]
    pressure: Mapped[str | None]  # Low | Medium | High

    overlay_key: Mapped[str | None]
    mask_key: Mapped[str | None]  # PNG label mask: 0 soil, 1 crop, 2 weed
    grid: Mapped[list[list[float]] | None] = mapped_column(JSON)  # densities: 0..1
    spray_cells: Mapped[list[list[int]] | None] = mapped_column(JSON)  # [row, col]

    blanket_cost: Mapped[float | None]
    spot_cost: Mapped[float | None]
    saved_litres: Mapped[float | None]
    saved_pct: Mapped[float | None]
    processing_ms: Mapped[int | None]

    scan: Mapped[Scan] = relationship(back_populates="results")
