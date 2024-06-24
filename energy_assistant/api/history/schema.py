"""Schemas for home measurement api."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class DeviceMeasurementPeriodSchema(BaseModel):
    """Schema class for a device measurement."""

    device_id: uuid.UUID

    solar_consumed_energy: float
    consumed_energy: float

    model_config = ConfigDict(from_attributes=True)


class HomeMeasurementPeriodSchema(BaseModel):
    """Schema class for a home measurement."""

    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float

    device_measurements: list[DeviceMeasurementPeriodSchema]

    model_config = ConfigDict(from_attributes=True)


class ReadHomeMeasurementDifferenceResponse(HomeMeasurementPeriodSchema):
    """API Response for reading home measurements."""


class HomeMeasurementDateSchema(HomeMeasurementPeriodSchema):
    """Schema class for a home measurement summary of a specific day."""

    measurement_date: date

    model_config = ConfigDict(from_attributes=True)


class HomeMeasurementDailySchema(BaseModel):
    """Schema class for daily home measurements."""

    measurements: list[HomeMeasurementDateSchema]

    model_config = ConfigDict(from_attributes=True)


class HomeMeasurementDailyResponse(HomeMeasurementDailySchema):
    """Schema for the daily home measurements response."""
