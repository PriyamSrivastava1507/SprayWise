"""Data access for scans and their results. No business rules."""

from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple, Optional, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import Method, ResultStatus
from app.models import Scan, ScanResult


class TrendRow(NamedTuple):
    scan_id: int
    created_at: datetime
    weed_pct: Optional[float]
    saved_pct: Optional[float]


class ScanRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _with_children():
        # Load results and field together, so building a response never
        # triggers one query per scan (the N+1 problem).
        return (selectinload(Scan.results), joinedload(Scan.field))

    def add(self, scan: Scan) -> Scan:
        """Persist a scan and its results in ONE commit. On failure the session
        is rolled back, so the caller can clean up files and carry on."""
        self.db.add(scan)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(scan)
        return scan

    def get(self, scan_id: int) -> Scan | None:
        query = select(Scan).where(Scan.id == scan_id).options(*self._with_children())
        return self.db.scalars(query).unique().first()

    def list(self, field_id: int | None, limit: int, offset: int) -> list[Scan]:
        query = (
            select(Scan)
            .options(*self._with_children())
            .order_by(Scan.created_at.desc(), Scan.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if field_id is not None:
            query = query.where(Scan.field_id == field_id)
        return list(self.db.scalars(query).unique())

    def count(self, field_id: int | None) -> int:
        query = select(func.count(Scan.id))
        if field_id is not None:
            query = query.where(Scan.field_id == field_id)
        return self.db.scalar(query) or 0

    def delete(self, scan: Scan) -> None:
        self.db.delete(scan)
        self.db.commit()

    # Sequence, not list: this class defines a method called `list`, which shadows the
    # built-in for every annotation written after it.
    def trend(self, field_id: int, method: Union[Method, str]) -> Sequence[TrendRow]:
        """Weed % and saved % over time for one field and one method.
        Only successful results: a failed run has no statistics to plot."""
        method_value = method.value if isinstance(method, Method) else str(method)
        query = (
            select(Scan.id, Scan.created_at, ScanResult.weed_pct, ScanResult.saved_pct)
            .join(ScanResult, ScanResult.scan_id == Scan.id)
            .where(
                Scan.field_id == field_id,
                ScanResult.method == method_value,
                ScanResult.status == ResultStatus.OK.value,
            )
            .order_by(Scan.created_at, Scan.id)
        )
        return [TrendRow(*row) for row in self.db.execute(query)]
