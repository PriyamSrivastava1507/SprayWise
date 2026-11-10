from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from app.models.field import Field
    from app.models.scan_result import ScanResult


class Scan(Base):
    """One uploaded image plus the parameters used to analyse it."""

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)
    mode: Mapped[str]
    original_key: Mapped[str]  # storage key, never a URL or absolute path
    width: Mapped[int]
    height: Mapped[int]
    area_ha: Mapped[float]
    dose_l_per_ha: Mapped[float]
    price_per_l: Mapped[float]
    grid_rows: Mapped[int]
    grid_cols: Mapped[int]
    cell_threshold: Mapped[float]

    field: Mapped[Field | None] = relationship(back_populates="scans")
    results: Mapped[list[ScanResult]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        order_by="ScanResult.id",
    )
