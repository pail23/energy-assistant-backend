"""Schemas for configuration api."""

from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Schema for the configuration."""

    config: dict


class ReadConfigResponse(ConfigModel):
    """API Response for reading the configuration."""


class ReadDeviceConfigResponse(ConfigModel):
    """API Response for reading the device configuration."""


class VersionModel(BaseModel):
    """Schema for the version."""

    version: str
    ui_version: str


class ReadVersionResponse(VersionModel):
    """API Response for reading the version."""


class DeviceControlModel(BaseModel):
    """Schema for the device control."""

    disable_device_control: bool


class ReadDeviceControlResponse(DeviceControlModel):
    """API Response for reading the device control."""
