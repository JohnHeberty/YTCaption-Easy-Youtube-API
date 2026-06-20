"""
Body size limit middleware for FastAPI/Starlette applications.
Rejects requests that exceed the configured max body size.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse


class BodySizeMiddleware(BaseHTTPMiddleware):
    """Middleware that rejects requests whose Content-Length exceeds max_size bytes."""

    def __init__(self, app: object, max_size: int) -> None:
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[object]]
    ) -> JSONResponse | object:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"Request body too large. "
                        f"Maximum: {self.max_size // 1024 // 1024}MB"
                    )
                },
            )
        return await call_next(request)
