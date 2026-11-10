"""Reading and deleting stored scans."""

import logging
from typing import Optional

from app.clients.base import StorageClient
from app.core.exceptions import NotFoundError
from app.repositories.scan_repository import ScanRepository
from app.schemas.common import Page
from app.schemas.scan import ScanDetail
from app.services.mappers import to_scan_detail

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(self, scans: ScanRepository, storage: StorageClient):
        self.scans = scans
        self.storage = storage

    def list(self, field_id: Optional[int], limit: int, offset: int) -> Page[ScanDetail]:
        rows = self.scans.list(field_id, limit, offset)
        return Page[ScanDetail](
            items=[to_scan_detail(scan, self.storage) for scan in rows],
            total=self.scans.count(field_id),
            limit=limit,
            offset=offset,
        )

    def get(self, scan_id: int) -> ScanDetail:
        scan = self.scans.get(scan_id)
        if scan is None:
            raise NotFoundError(f"Scan {scan_id} does not exist.")
        return to_scan_detail(scan, self.storage)

    def delete(self, scan_id: int) -> None:
        scan = self.scans.get(scan_id)
        if scan is None:
            raise NotFoundError(f"Scan {scan_id} does not exist.")
        keys = [scan.original_key]
        for result in scan.results:
            keys += [k for k in (result.overlay_key, result.mask_key) if k]
        self.scans.delete(scan)  # database first: a leftover file is harmless, a dangling row is not
        for key in keys:
            try:
                self.storage.delete(key)
            except Exception:
                logger.warning("could not delete %s for scan %s", key, scan_id, exc_info=True)
