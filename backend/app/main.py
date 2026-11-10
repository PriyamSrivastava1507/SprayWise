"""Application factory: wires settings, storage, the segmentation client,
routes, static media, CORS and the one error format."""

import logging
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.clients.factory import build_segmentation_client, build_storage_client
from app.core.config import Settings, settings as default_settings
from app.core.database import init_db
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _summarise(errors: Sequence[Any]) -> str:
    """'field: problem; field: problem' - readable, and never echoes input values."""
    parts = []
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "form"))
        parts.append(f"{loc}: {err.get('msg', 'invalid value')}" if loc else str(err.get("msg")))
    return "; ".join(parts) or "Invalid request."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", _summarise(exc.errors()))

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(_: Request, exc: ValidationError) -> JSONResponse:
        return _error(422, "validation_error", _summarise(exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled error on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return _error(500, "internal_error", "Something went wrong on the server.")


def create_app(
    settings: Optional[Settings] = None,
    init_database: bool = True,
) -> FastAPI:
    cfg = settings or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        os.makedirs(cfg.storage_dir, exist_ok=True)
        if init_database:
            init_db()
        app.state.settings = cfg
        app.state.storage = build_storage_client(cfg)
        app.state.segmenter = build_segmentation_client(cfg)
        logger.info(
            "segmentation backend=%s model=%s ready=%s",
            app.state.segmenter.backend,
            app.state.segmenter.model_id,
            app.state.segmenter.is_ready(),
        )
        yield

    app = FastAPI(
        title="SprayWise API",
        version="1.0.0",
        description="Crop/weed segmentation and spot-spraying decision support.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    # Mounted at creation time (the folder must exist), served by Starlette.
    os.makedirs(cfg.storage_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=cfg.storage_dir), name="media")
    return app


app = create_app()
