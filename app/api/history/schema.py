"""Schemas for home measurement api."""

import uuid

from pydantic import BaseModel, ConfigDict


class DeviceMeasurementDifferenceSchema(BaseModel):
    """Schema class for a device measurement."""

    #name: str
    device_id: uuid.UUID

    solar_consumed_energy: float
    consumed_energy: float

    model_config = ConfigDict(from_attributes=True)



class HomeMeasurementDifferenceSchema(BaseModel):
    """Schema class for a home measurement."""

    name: str
    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float

    device_measurements: list[DeviceMeasurementDifferenceSchema]

    model_config = ConfigDict(from_attributes=True)

class ReadHomeMeasurementDifferenceResponse(HomeMeasurementDifferenceSchema):
    """API Response for reading home measurements."""

    pass
