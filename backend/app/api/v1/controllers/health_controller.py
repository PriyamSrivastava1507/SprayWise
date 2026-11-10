import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbDep, SegmenterDep, SettingsDep
from app.schemas.health import HealthResponse, ModelStatus, PressureThresholds

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Service, database and model status")
def health(db: DbDep, segmenter: SegmenterDep, settings: SettingsDep) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.exception("health check: database unreachable")
        database = "error"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        model=ModelStatus(
            backend=segmenter.backend,
            model_id=segmenter.model_id,
            ready=segmenter.is_ready(),
            detail=segmenter.detail,
        ),
        pressure_thresholds=PressureThresholds(
            low_max=settings.pressure_low_max,
            high_min=settings.pressure_high_min,
        ),
    )
