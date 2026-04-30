"""
Main routes configuration for YouTube Search service.
"""

from fastapi import APIRouter

from . import search
from . import jobs
from . import admin

router = APIRouter()

# Include sub-routers with prefixes
router.include_router(search.router, prefix="/search", tags=["Search"])
router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
router.include_router(admin.router, tags=["Admin"])
