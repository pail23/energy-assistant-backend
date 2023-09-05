"""Schemas for home measurement api."""

from datetime import datetime

from pydantic import BaseModel


class ForecastSchema(BaseModel):
    """Schema for the forecast."""

    time: list[datetime]
    series: dict[str, list[float]]


class ReadForecastResponse(ForecastSchema):
    """API Response for reading the forecast."""

    pass
