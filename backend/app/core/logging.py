"""Logging setup and a request-logging middleware."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

access_logger = logging.getLogger("spraywise.access")


def configure_logging(level: str = "INFO") -> None:
    """One readable line per event, to stdout (what Docker and hosts collect)."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status and time for every request, and tags it with
    an id (X-Request-ID) so a user's error can be found in the logs.
    Never logs bodies, query strings or uploaded files."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            access_logger.info(
                "%s %s -> %s %dms id=%s",
                request.method,
                request.url.path,
                status,
                (time.perf_counter() - started) * 1000,
                request_id,
            )
