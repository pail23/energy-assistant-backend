"""Schemas for home measurement api."""

from datetime import date
import uuid

from pydantic import BaseModel, ConfigDict


class DeviceMeasurementDifferenceSchema(BaseModel):
    """Schema class for a device measurement."""

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



class DeviceMeasurementDateSchema(BaseModel):
    """Schema class for a device measurement of a specific day."""

    device_id: uuid.UUID

    solar_consumed_energy: float
    consumed_energy: float

    model_config = ConfigDict(from_attributes=True)

class HomeMeasurementDateSchema(BaseModel):
    """Schema class for a home measurement summary of a specific day."""

    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float
    measurement_date: date

    device_measurements: list[DeviceMeasurementDateSchema]

    model_config = ConfigDict(from_attributes=True)




class HomeMeasurementDailySchema(BaseModel):
    """Schema class for daily home measurements."""

    measurements: list[HomeMeasurementDateSchema]

    model_config = ConfigDict(from_attributes=True)

class HomeMeasurementDailyResponse(HomeMeasurementDailySchema):
    """Schema for the daily home measurements response."""

    pass
