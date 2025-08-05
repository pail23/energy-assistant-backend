"""Test the config storage."""

from pathlib import Path

import pytest

from energy_assistant.settings import settings
from energy_assistant.storage.config import (
    ConfigSectionStorage,
    ConfigStorage,
)


@pytest.mark.asyncio()
async def test_config_section_storage() -> None:
    """Test section config data storage."""
    config = ConfigSectionStorage(Path(settings.DATA_FOLDER), "home")
    config.delete_config_file()
    await config.initialize(Path(__file__).parent / "config.yaml")
    assert config.get("name") == "my home"
    config.set("name", "my great home")
    assert config.get("name") == "my great home"


@pytest.mark.asyncio()
async def test_config_storage() -> None:
    """Test config data storage."""
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    await config.initialize(Path(__file__).parent / "config.yaml")
    assert config.home.get("name") == "my home"
