"""Use cases for devices."""

import logging
import uuid

from energy_assistant_frontend import __version__ as front_end_version
from fastapi import HTTPException

from energy_assistant import __version__
from energy_assistant.api.config.schema import ConfigModel, DeviceControlModel, VersionModel
from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.db import AsyncSession
from energy_assistant.devices.config import EnergyAssistantConfig
from energy_assistant.devices.home import Home
from energy_assistant.models.device import Device

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class ReadConfiguration:
    """Read the configuration use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read configuration use case."""
        self.async_session = session

    async def execute(self, config: EnergyAssistantConfig) -> ConfigModel:
        """Execute the read configuration use case."""
        return ConfigModel.model_validate({"config": config.as_dict})


class ReadVersion:
    """Read the version use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read version use case."""
        self.async_session = session

    async def execute(self) -> VersionModel:
        """Execute the read configuration use case."""
        return VersionModel.model_validate({"version": __version__, "ui_version": front_end_version})


class ReadDeviceControl:
    """Read the device control use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read device control use case."""
        self.async_session = session

    async def execute(self, home: Home) -> DeviceControlModel:
        """Execute the read configuration use case."""
        return DeviceControlModel.model_validate({"disable_device_control": home.disable_device_control})


class WriteDeviceControl:
    """Write the device control use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a write device control use case."""
        self.async_session = session

    async def execute(self, disable_device_control: bool, home: Home) -> DeviceControlModel:
        """Execute the write configuration use case."""
        home.set_disable_device_control(disable_device_control)
        return DeviceControlModel.model_validate({"disable_device_control": home.disable_device_control})


class ReadDeviceConfiguration:
    """Read the configuration use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read configuration use case."""
        self.async_session = session

    async def execute(self, config: EnergyAssistantConfig, device_id: uuid.UUID) -> ConfigModel:
        """Execute the read configuration use case."""
        async with self.async_session.begin() as session:
            persisted_device = await Device.read_by_id(session, device_id)
            if persisted_device is None:
                raise HTTPException(status_code=404)
            return ConfigModel.model_validate({"config": persisted_device.get_config()})


class WriteDeviceConfiguration:
    """Write the configuration values on a device."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a write configuration use case."""
        self.async_session = session

    async def execute(self, config: EnergyAssistantConfig, data: dict, device_id: uuid.UUID, home: Home) -> ConfigModel:
        """Execute the write configuration use case."""
        async with self.async_session.begin() as session:
            device = home.get_device(device_id)
            persisted_device = await Device.read_by_id(session, device_id)
            if persisted_device is None:
                raise HTTPException(status_code=404)

            new_config = device.config if device is not None else {}
            for key, value in data.items():
                new_config[key] = value

            device_name = data.get("name", persisted_device.name)
            device_icon = data.get("icon", persisted_device.icon)
            device_type = persisted_device.type or ""
            await persisted_device.update(
                session, device_name, device_icon, persisted_device.power_mode, device_type, new_config
            )
            if device is not None:
                device.configure(new_config)
            return ConfigModel.model_validate({"config": new_config})
