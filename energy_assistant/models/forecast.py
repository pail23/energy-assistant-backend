"""Forecast data models."""

from datetime import datetime

from pydantic import BaseModel


class ForecastSerieSchema(BaseModel):
    """Schema for a forecast data series."""

    name: str
    data: list[float]


class ForecastSchema(BaseModel):
    """Schema for the forecast."""

    cost: float
    solar_energy: float
    consumed_energy: float
    time: list[datetime]
    series: list[ForecastSerieSchema]
