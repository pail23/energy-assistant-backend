"""Schemas for home measurement api."""

from pydantic import BaseModel

from energy_assistant.models.schema import DeviceMeasurementSchema, DeviceSchema


class ReadDeviceResponse(DeviceSchema):
    """API Response for reading a device."""


class ReadAllDevicesResponse(BaseModel):
    """API Response for reading all deviced."""

    devices: list[DeviceSchema]


class ReadDeviceMeasurementsResponse(BaseModel):
    """API Response for reading home measurements."""

    device_measurements: list[DeviceMeasurementSchema]


class UpdateDevicePowerModeRequest(BaseModel):
    """API Request for setting the power mode."""

    power_mode: str


class UpdateDevicePowerModeResponse(DeviceSchema):
    """API Response for setting the power mode."""


class CreateDeviceRequest(BaseModel):
    """API Request for creating a device."""

    device_type: str


class CreateDeviceResponse(BaseModel):
    """API Response for creating a device."""

    device_id: str
