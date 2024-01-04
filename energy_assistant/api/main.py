"""Main api module."""

from fastapi import APIRouter

from .config.views import router as config_router
from .device.views import router as device_router
from .forecast.views import router as forecast_router
from .history.views import router as history_router
from .home_measurement.views import router as home_measurement_router
from .sessionlogs.views import router as session_log_router

router = APIRouter()

router.include_router(device_router)
router.include_router(home_measurement_router)
router.include_router(history_router)
router.include_router(session_log_router)
router.include_router(forecast_router)
router.include_router(config_router)
