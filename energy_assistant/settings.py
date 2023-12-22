"""The settings for the Energy Assistant-."""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Energy Assistant."""

    DB_URI: str
    ECHO_SQL: bool
    CONFIG_FILE: str
    DEVICE_TYPE_REGISTRY: str
    LOG_FILE: str
    DATA_FOLDER: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / f"config/{os.environ['APP_CONFIG_FILE']}.env",
        case_sensitive=True,
    )


settings = Settings.model_validate({})
