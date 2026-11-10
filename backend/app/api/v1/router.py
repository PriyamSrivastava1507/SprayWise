from fastapi import APIRouter

from app.api.v1.controllers import (
    analysis_controller,
    evaluation_controller,
    exports_controller,
    fields_controller,
    health_controller,
    scans_controller,
)

api_router = APIRouter()
api_router.include_router(analysis_controller.router)
api_router.include_router(scans_controller.router)
api_router.include_router(fields_controller.router)
api_router.include_router(exports_controller.router)
api_router.include_router(evaluation_controller.router)
api_router.include_router(health_controller.router)
