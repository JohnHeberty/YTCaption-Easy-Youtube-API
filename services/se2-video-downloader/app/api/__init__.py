from .jobs_routes import router as jobs_router
from .admin_routes import router as admin_router
from .health_routes import router as health_router

__all__ = ["jobs_router", "admin_router", "health_router"]