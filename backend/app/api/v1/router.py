from fastapi import APIRouter

from app.api.v1.controllers import analysis_controller

api_router = APIRouter()
api_router.include_router(analysis_controller.router)
