import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbDep, ModelsDep, SettingsDep
from app.clients.registry import LoadedModel, ModelRegistry
from app.schemas.health import HealthResponse, ModelInfo, ModelStatus, PressureThresholds

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _info(model: LoadedModel, registry: ModelRegistry) -> ModelInfo:
    client = model.client
    return ModelInfo(
        key=model.key,
        label=model.label,
        default=model.key == registry.default_key,
        backend=client.backend,
        model_id=client.model_id,
        ready=client.is_ready(),
        detail=client.detail,
    )


@router.get("/health", response_model=HealthResponse, summary="Service, database and model status")
def health(db: DbDep, models: ModelsDep, settings: SettingsDep) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.exception("health check: database unreachable")
        database = "error"
    default = models.default.client
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        model=ModelStatus(
            backend=default.backend,
            model_id=default.model_id,
            ready=default.is_ready(),
            detail=default.detail,
        ),
        models=[_info(m, models) for m in models],
        pressure_thresholds=PressureThresholds(
            low_max=settings.pressure_low_max,
            high_min=settings.pressure_high_min,
        ),
    )


@router.get("/models", response_model=list[ModelInfo], summary="The ML models this server can run")
def list_models(models: ModelsDep) -> list[ModelInfo]:
    return [_info(m, models) for m in models]
