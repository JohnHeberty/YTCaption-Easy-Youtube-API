"""
API routes for the orchestrator service.
"""

from .pipeline_routes import router as pipeline_router
from .health_routes import router as health_router
from .admin_routes import router as admin_router
from .jobs_routes import router as jobs_router

__all__ = ["pipeline_router", "health_router", "admin_router", "jobs_router"]