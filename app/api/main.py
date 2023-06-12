"""Main api module."""

from fastapi import APIRouter

from .home_measurement.views import router as home_measurement_router

router = APIRouter()

router.include_router(home_measurement_router)
