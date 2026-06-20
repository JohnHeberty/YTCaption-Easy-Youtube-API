"""
API routes for the orchestrator service.
"""

from .health_routes import router as health_router
from .admin_routes import router as admin_router
from .jobs_routes import router as jobs_router

__all__ = ["health_router", "admin_router", "jobs_router"]