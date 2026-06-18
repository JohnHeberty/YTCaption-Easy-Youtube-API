"""
FastAPI application factory for YTCaption microservices.

Standardizes:
- Lifespan composition (base + service-specific)
- Exception handlers (shared or custom)
- CORS middleware
- Rate limiting middleware
- Body size middleware
- API key authentication dependency
- Router registration

Usage:
    from common.fastapi_utils import create_service_app, create_api_key_dependency

    app = create_service_app(
        service_name="my-service",
        title="My Service",
        version="1.0.0",
        settings=settings,
        lifespan=lifespan,
        setup_routers=lambda a: a.include_router(my_router),
    )
"""
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Sequence

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from common.exception_handlers import setup_exception_handlers
from common.log_utils import get_logger
from common.middleware import BodySizeMiddleware, RateLimiterMiddleware


def create_service_app(
    *,
    service_name: str,
    title: str,
    description: str = "",
    version: str = "1.0.0",
    settings: Optional[Dict[str, Any]] = None,
    lifespan: Optional[Callable[[FastAPI], AsyncIterator[None]]] = None,
    setup_routers: Optional[Callable[[FastAPI], None]] = None,
    use_shared_exception_handlers: bool = True,
    cors_options: Optional[Dict[str, Any]] = None,
    rate_limit_options: Optional[Dict[str, Any]] = None,
    body_size_mb: Optional[int] = None,
    **fastapi_kwargs: Any,
) -> FastAPI:
    """Create a configured FastAPI application.

    Args:
        service_name: Logical name for logging/health checks.
        title: FastAPI ``title``.
        description: FastAPI ``description``.
        version: FastAPI ``version``.
        settings: Service settings dict. Used to extract middleware config
            when explicit options are not provided.
        lifespan: Service-specific lifespan async generator.
        setup_routers: Callback to register routers on the app.
        use_shared_exception_handlers: If True, calls
            ``setup_exception_handlers(app, debug=...)``.
        cors_options: Passed directly to ``CORSMiddleware`` (e.g.
            ``allow_origins``, ``allow_methods``). When None, extracted
            from ``settings["cors"]`` if available.
        rate_limit_options: Passed to ``RateLimiterMiddleware`` (keys
            ``max_requests``, ``window_seconds``). When None, extracted
            from ``settings["rate_limit"]`` if available.
        body_size_mb: Max request body in MB. Passed to
            ``BodySizeMiddleware``. When None, extracted from
            ``settings["max_file_size_mb"]`` if available.
        **fastapi_kwargs: Additional kwargs forwarded to ``FastAPI()``.

    Returns:
        Configured ``FastAPI`` instance.
    """
    logger = get_logger(__name__)
    debug = _get(settings, "debug", False)
    composed_lifespan = _compose_lifespan(service_name, title, lifespan)

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=composed_lifespan,
        **fastapi_kwargs,
    )

    # --- Exception handlers -------------------------------------------
    if use_shared_exception_handlers:
        setup_exception_handlers(app, debug=debug)
        logger.debug("Shared exception handlers registered")

    # --- CORS ---------------------------------------------------------
    cors_kwargs = _resolve_cors(cors_options, settings)
    if cors_kwargs is not None:
        app.add_middleware(CORSMiddleware, **cors_kwargs)

    # --- Rate limiter -------------------------------------------------
    rl_kwargs = _resolve_rate_limit(rate_limit_options, settings)
    if rl_kwargs is not None:
        app.add_middleware(RateLimiterMiddleware, **rl_kwargs)

    # --- Body size ----------------------------------------------------
    body_bytes = _resolve_body_size(body_size_mb, settings)
    if body_bytes is not None:
        app.add_middleware(BodySizeMiddleware, max_size=body_bytes)

    # --- Routers ------------------------------------------------------
    if setup_routers is not None:
        setup_routers(app)

    logger.info(
        "App created | service=%s title=%s version=%s",
        service_name, title, version,
    )
    return app


# ------------------------------------------------------------------ #
#  Internal helpers
# ------------------------------------------------------------------ #


def _get(settings: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    """Safely read a key from an optional dict-like settings."""
    if settings is None:
        return default
    if isinstance(settings, dict):
        return settings.get(key, default)
    return getattr(settings, key, default)


def _compose_lifespan(
    service_name: str,
    title: str,
    service_lifespan: Optional[Callable[[FastAPI], AsyncIterator[None]]] = None,
) -> Callable[[FastAPI], AsyncIterator[None]]:
    """Wrap a service-specific lifespan with startup/shutdown logging."""
    logger = get_logger(__name__)

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            logger.info("Starting %s (%s)", title, service_name)
            if service_lifespan is not None:
                async with service_lifespan(app):
                    yield
            else:
                yield
        except Exception:
            logger.exception("Fatal error during %s lifecycle", service_name)
            raise
        finally:
            logger.info("%s stopped", title)

    return _lifespan


def _resolve_cors(
    explicit: Optional[Dict[str, Any]],
    settings: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve CORS middleware arguments."""
    if explicit is not None:
        return explicit
    cors_cfg = _get(settings, "cors")
    if isinstance(cors_cfg, dict) and cors_cfg.get("enabled", True):
        return {
            "allow_origins": cors_cfg.get("origins", ["*"]),
            "allow_credentials": cors_cfg.get("credentials", True),
            "allow_methods": cors_cfg.get("methods", ["*"]),
            "allow_headers": cors_cfg.get("headers", ["*"]),
        }
    return None


def _resolve_rate_limit(
    explicit: Optional[Dict[str, Any]],
    settings: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve RateLimiterMiddleware arguments."""
    if explicit is not None:
        return explicit
    rl = _get(settings, "rate_limit")
    if isinstance(rl, dict) and rl.get("enabled", True):
        return {
            "max_requests": rl.get("max_requests", 100),
            "window_seconds": rl.get("window_seconds", 60),
        }
    return None


def _resolve_body_size(
    explicit_mb: Optional[int],
    settings: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Resolve body size in bytes."""
    if explicit_mb is not None:
        return explicit_mb * 1024 * 1024
    mb = _get(settings, "max_file_size_mb")
    if mb is not None:
        return int(mb) * 1024 * 1024
    return None


# ------------------------------------------------------------------ #
#  API Key Authentication
# ------------------------------------------------------------------ #

_DEFAULT_EXEMPT_PATHS = frozenset({"/", "/health", "/health/deep", "/ping"})


def create_api_key_dependency(
    api_key: Optional[str],
    exempt_paths: Optional[List[str]] = None,
) -> Callable:
    """Create a FastAPI dependency that validates ``X-API-Key`` header.

    Args:
        api_key: Expected API key value.  When ``None``, authentication is
            **disabled** (all requests pass through).
        exempt_paths: URL paths that bypass authentication.  Defaults to
            common health endpoints (``/``, ``/health``, ``/health/deep``,
            ``/ping``).

    Returns:
        An async dependency function suitable for use with
        ``FastAPI.dependencies`` or ``Depends()``.

    Example::

        from common.fastapi_utils import create_api_key_dependency

        verify = create_api_key_dependency(api_key=settings.api_key)

        app = create_service_app(
            ...,
            dependencies=[Depends(verify)],
        )
    """
    paths = frozenset(exempt_paths) if exempt_paths is not None else _DEFAULT_EXEMPT_PATHS

    async def _verify(request: Request) -> None:
        if not api_key:
            return
        if request.url.path in paths:
            return
        key = request.headers.get("X-API-Key")
        if key != api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return _verify
