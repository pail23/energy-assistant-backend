"""Test the config storage."""

import uuid
from pathlib import Path

import pytest

from energy_assistant.settings import settings
from energy_assistant.storage.config import (
    ConfigSectionStorage,
    ConfigStorage,
    DeviceConfigStorage,
    DeviceNotFoundError,
)


@pytest.mark.asyncio()
async def test_config_section_storage() -> None:
    """Test section config data storage."""
    config = ConfigSectionStorage(Path(settings.DATA_FOLDER), "home")
    config.delete_config_file()
    await config.initialize(Path(__file__).parent/"config.yaml")
    assert config.get("name") == "my home"
    config.set("name", "my great home")
    assert config.get("name") == "my great home"

@pytest.mark.asyncio()
async def test_devices_config_section_storage() -> None:
    """Test device config data storage."""
    config = DeviceConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()
    await config.initialize(Path(__file__).parent/"config.yaml")

    device = config.get_device_config(uuid.UUID("a3a3e2c5-df55-44eb-b75a-a432dcec92a6"))
    assert len(device) == 10

    config.set(uuid.UUID("a3a3e2c5-df55-44eb-b75a-a432dcec92a6"), "nominal_power", 123)
    assert config.get(uuid.UUID("a3a3e2c5-df55-44eb-b75a-a432dcec92a6"), "nominal_power") == 123
    assert config.get(uuid.UUID("a3a3e2c5-df55-44eb-b75a-a432dcec92a6"), "nominal_duration") == 7200


    with pytest.raises(DeviceNotFoundError):
        config.set(uuid.UUID("7b508283-29da-40a4-8955-e1f7693a5354"), "nominal_power", 456)
    with pytest.raises(DeviceNotFoundError):
        config.get(uuid.UUID("7b508283-29da-40a4-8955-e1f7693a5354"), "nominal_power")


@pytest.mark.asyncio()
async def test_config_storage() -> None:
    """Test config data storage."""
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    await config.initialize(Path(__file__).parent/"config.yaml")
    assert config.home.get("name") == "my home"
