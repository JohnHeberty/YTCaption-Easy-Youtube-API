import logging
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from projeto_v3.app.config import get_settings
from projeto_v3.adapters.inbound.api import router as api_router


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        default_response_class=ORJSONResponse,
    )
    app.state.settings = settings

    # Rotas HTTP
    app.include_router(api_router)
    return app


app = create_app()
