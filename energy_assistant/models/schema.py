"""Schemas for all the models."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class DeviceMeasurementSchema(BaseModel):
    """Schema class for a device measurement."""

    id: int
    # name: str
    solar_consumed_energy: float
    consumed_energy: float
    home_measurement_id: int
    device_id: uuid.UUID
    measurement_date: datetime.date | None

    model_config = ConfigDict(from_attributes=True)


class DeviceSchema(BaseModel):
    """Schema class for a device."""

    id: uuid.UUID
    name: str
    icon: str
    type: str
    config: str
    supported_power_modes: list[str] | None = None
    power_mode: str | None = None

    model_config = ConfigDict(from_attributes=True)


class HomeMeasurementSchema(BaseModel):
    """Schema class for a home measurement."""

    id: int
    name: str
    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float
    measurement_date: datetime.date

    device_measurements: list[DeviceMeasurementSchema]

    model_config = ConfigDict(from_attributes=True)
