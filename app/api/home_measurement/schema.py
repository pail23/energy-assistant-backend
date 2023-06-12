"""Schemas for home measurement api."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.home import HomeMeasurementSchema


class ReadHomeMeasurementResponse(HomeMeasurementSchema):
    """API Response for reading home measurements."""

    pass


class ReadAllHomeMeasurementResponse(BaseModel):
    """API Response for reading home measurements."""

    home_measurements: list[HomeMeasurementSchema]
