"""Turn database entities into response schemas, so ORM objects never leave the
service layer and storage keys become URLs in exactly one place."""

from app.clients.base import StorageClient
from app.models import Scan, ScanResult
from app.schemas.scan import (
    FieldRef,
    Savings,
    ScanDetail,
    ScanParams,
    ScanResultOut,
)


def _savings(result: ScanResult, scan: Scan) -> Savings:
    if result.saved_litres is None or result.blanket_cost is None or result.spot_cost is None:
        return Savings()
    blanket_litres = round(scan.area_ha * scan.dose_l_per_ha, 2)
    return Savings(
        blanket_litres=blanket_litres,
        spot_litres=round(max(blanket_litres - result.saved_litres, 0.0), 2),
        saved_litres=result.saved_litres,
        blanket_cost=result.blanket_cost,
        spot_cost=result.spot_cost,
        saved_cost=round(result.blanket_cost - result.spot_cost, 2),
        saved_pct=result.saved_pct,
    )


def to_result_out(result: ScanResult, scan: Scan, storage: StorageClient) -> ScanResultOut:
    return ScanResultOut(
        method=result.method,
        status=result.status,
        status_detail=result.status_detail,
        model_id=result.model_id,
        vegetation_pct=result.vegetation_pct,
        crop_pct=result.crop_pct,
        weed_pct=result.weed_pct,
        pressure=result.pressure,
        overlay_url=storage.url(result.overlay_key) if result.overlay_key else None,
        mask_url=storage.url(result.mask_key) if result.mask_key else None,
        grid=result.grid,
        spray_cells=result.spray_cells,
        savings=_savings(result, scan),
        processing_ms=result.processing_ms,
    )


def to_scan_detail(scan: Scan, storage: StorageClient) -> ScanDetail:
    return ScanDetail(
        id=scan.id,
        field=FieldRef(id=scan.field.id, name=scan.field.name) if scan.field else None,
        created_at=scan.created_at,
        mode=scan.mode,
        width=scan.width,
        height=scan.height,
        original_url=storage.url(scan.original_key),
        params=ScanParams(
            area_ha=scan.area_ha,
            dose_l_per_ha=scan.dose_l_per_ha,
            price_per_l=scan.price_per_l,
            grid_rows=scan.grid_rows,
            grid_cols=scan.grid_cols,
            cell_threshold=scan.cell_threshold,
        ),
        results=[to_result_out(result, scan, storage) for result in scan.results],
    )
