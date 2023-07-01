"""Schemas for home measurement api."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class DeviceMeasurementDifferenceSchema(BaseModel):
    """Schema class for a device measurement."""

    #name: str
    device_id: uuid.UUID

    solar_consumed_energy: float
    consumed_energy: float

    class Config:
        """Config class for the Device Measurement Scheme."""

        orm_mode = True



class HomeMeasurementDifferenceSchema(BaseModel):
    """Schema class for a home measurement."""

    name: str
    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float

    device_measurements: list[DeviceMeasurementDifferenceSchema]

    class Config:
        """Config class for the Home Measurement Scheme."""

        orm_mode = True

class ReadHomeMeasurementDifferenceResponse(HomeMeasurementDifferenceSchema):
    """API Response for reading home measurements."""

    pass
