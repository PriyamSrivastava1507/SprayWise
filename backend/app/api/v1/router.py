from fastapi import APIRouter

from app.api.v1.controllers import analysis_controller, fields_controller, scans_controller

api_router = APIRouter()
api_router.include_router(analysis_controller.router)
api_router.include_router(scans_controller.router)
api_router.include_router(fields_controller.router)
