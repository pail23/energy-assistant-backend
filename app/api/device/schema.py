"""Schemas for home measurement api."""

from pydantic import BaseModel

from app.models import DeviceMeasurementSchema, DeviceSchema


class ReadDeviceResponse(DeviceSchema):
    """API Response for reading a device."""

    pass


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

    pass
