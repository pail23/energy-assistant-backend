"""Main api module."""

from fastapi import APIRouter

from .device.views import router as device_router
from .history.views import router as history_router
from .home_measurement.views import router as home_measurement_router

router = APIRouter()

router.include_router(device_router)
router.include_router(home_measurement_router)
router.include_router(history_router)
