"""Schemas for home measurement api."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.device import DeviceSchema


class ReadDeviceResponse(DeviceSchema):
    """API Response for reading a device."""

    pass


class ReadAllDevicesResponse(BaseModel):
    """API Response for reading all deviced."""

    devices: list[DeviceSchema]
