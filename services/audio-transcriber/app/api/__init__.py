from app.api.jobs_routes import router as jobs_router
from app.api.admin_routes import router as admin_router
from app.api.model_routes import router as model_router
from app.api.health_routes import router as health_router

__all__ = ["jobs_router", "admin_router", "model_router", "health_router"]