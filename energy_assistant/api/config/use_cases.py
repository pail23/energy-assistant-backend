"""Use cases for devices."""

import logging
import uuid

from fastapi import HTTPException

from energy_assistant.api.config.schema import ConfigModel
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


class ReadDeviceConfiguration:
    """Read the configuration use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read configuration use case."""
        self.async_session = session

    async def execute(self, config: EnergyAssistantConfig, device_id: uuid.UUID) -> ConfigModel:
        """Execute the read configuration use case."""
        return ConfigModel.model_validate(
            {"config": config.energy_assistant_config.devices.get_device_config(device_id)}
        )


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
            if device is None or persisted_device is None:
                raise HTTPException(status_code=404)

            for key, value in data.items():
                config.energy_assistant_config.devices.set(device_id, key, value)

            new_configuration = config.energy_assistant_config.devices.get_device_config(device_id)

            device_name = data.get("name", persisted_device.name)
            device_icon = data.get("icon", persisted_device.icon)
            device_type = data.get("type", persisted_device.type)
            await persisted_device.update(
                session, device_name, device_icon, persisted_device.power_mode, device_type, data
            )
            device.configure(new_configuration)
            return ConfigModel.model_validate({"config": new_configuration})
