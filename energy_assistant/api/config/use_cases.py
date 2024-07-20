"""Use cases for devices."""

import logging
import uuid

from energy_assistant.api.config.schema import ConfigModel
from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.db import AsyncSession
from energy_assistant.devices.config import EnergyAssistantConfig

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
        return ConfigModel.model_validate({"config": config.energy_assistant_config.devices.get_device_config(device_id)})


class WriteDeviceConfiguration:
    """Write the configuration values on a device."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a write configuration use case."""
        self.async_session = session

    async def execute(self, config: EnergyAssistantConfig, data: dict, device_id: uuid.UUID) -> ConfigModel:
        """Execute the write configuration use case."""
        for (key, value) in data.items():
            config.energy_assistant_config.devices.set(device_id, key, value)

        return ConfigModel.model_validate({"config": config.energy_assistant_config.devices.get_device_config(device_id)})
