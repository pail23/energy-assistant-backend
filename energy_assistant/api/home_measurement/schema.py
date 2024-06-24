"""Schemas for home measurement api."""

from pydantic import BaseModel

from energy_assistant.models.schema import HomeMeasurementSchema


class ReadHomeMeasurementResponse(HomeMeasurementSchema):
    """API Response for reading home measurements."""


class ReadAllHomeMeasurementResponse(BaseModel):
    """API Response for reading home measurements."""

    home_measurements: list[HomeMeasurementSchema]
