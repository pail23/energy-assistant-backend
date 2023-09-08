"""Forecast data models."""
from datetime import datetime

from pydantic import BaseModel


class ForecastSerieSchema(BaseModel):
    """Schema for a forcast data serie."""

    name: str
    data: list[float]

class ForecastSchema(BaseModel):
    """Schema for the forecast."""

    time: list[datetime]
    series: list[ForecastSerieSchema]
