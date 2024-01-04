"""Schemas for home measurement api."""

from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Schema for the configuration."""

    config: dict


class ReadConfigResponse(ConfigModel):
    """API Response for reading the configuration."""

    pass
