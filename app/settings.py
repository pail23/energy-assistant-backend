"""The settings for the Energy Assistant-."""
import os
from pathlib import Path

from pydantic import BaseSettings


class Settings(BaseSettings):
    """Settings for the Energy Assistant."""

    DB_URI: str
    ECHO_SQL: bool

    class Config:
        """Config for the Energy Assistant Settings."""

        env = os.environ["APP_CONFIG_FILE"]
        env_file = Path(__file__).parent / f"config/{env}.env"
        case_sensitive = True


settings = Settings.parse_obj({})
