"""Main api module."""

from fastapi import APIRouter

from .history.views import router as history_router
from .home_measurement.views import router as home_measurement_router

router = APIRouter()

router.include_router(home_measurement_router)
router.include_router(history_router)
