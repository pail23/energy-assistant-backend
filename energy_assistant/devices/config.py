"""Config helper classes and functions."""

from energy_assistant.devices import Location
from energy_assistant.storage.config import ConfigStorage, DeviceConfigMissingParameterError


def get_config_param(config: dict, param: str) -> str:
    """Get a config parameter as string or raise an exception if the parameter is not available."""
    result = config.get(param)
    if result is None:
        raise DeviceConfigMissingParameterError(param)
    return str(result)


def get_config_param_from_list(config: list, param: str) -> str | None:
    """Read config param from a list."""
    for item in config:
        value = item.get(param)
        if value is not None:
            return value
    return None


def get_float_param_from_list(config: list, param: str) -> float | None:
    """Read a float config param from a list."""
    for item in config:
        value = item.get(param)
        if value is not None:
            return float(value)
    return None


class EnergyAssistantConfig:
    """The energy assistant config."""

    def __init__(self, energy_assistant_config: ConfigStorage, hass_config: dict) -> None:
        """Create a EnergyAssistantConfig instance."""
        self._energy_assistant_config = energy_assistant_config
        self._hass_config = hass_config

    @property
    def as_dict(self) -> dict:
        """Get the complete config."""
        result = {
            "energy_assistant": self._energy_assistant_config.as_dict(),
            "home_assistant": self._hass_config,
        }
        result["emhass"] = self._energy_assistant_config.emhass.as_dict()
        del result["energy_assistant"]["emhass"]
        return result

    @property
    def energy_assistant_config(self) -> ConfigStorage:
        """Get the energy assistant config."""
        return self._energy_assistant_config

    @property
    def home_assistant_config(self) -> dict:
        """Get the home assistant config."""
        return self._hass_config

    @property
    def emhass_config(self) -> dict:
        """Get the emhass config."""
        return self._energy_assistant_config.emhass.as_dict()

    @property
    def location(self) -> Location:
        """Read the location from the Homeassistant configuration."""
        config = self.home_assistant_config

        return Location(
            latitude=config.get("latitude", ""),
            longitude=config.get("longitude", ""),
            elevation=config.get("elevation", ""),
            time_zone=config.get("time_zone", ""),
        )
