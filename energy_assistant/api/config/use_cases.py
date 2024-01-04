"""Use cases for devices."""
import logging

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
        result = ConfigModel.model_validate({"config": config.config})
        return result
