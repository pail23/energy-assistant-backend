"""Config helper classes and funtions."""


from energy_assistant.devices import Location


class DeviceConfigException(Exception):
    """Device configuration exception."""

    pass


def get_config_param(config: dict, param: str) -> str:
    """Get a config paramter as string or raise an exception if the parameter is not available."""
    result = config.get(param)
    if result is None:
        raise DeviceConfigException(f"Parameter {param} is missing in the configuration")
    else:
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

    def __init__(self, energy_assistant_config: dict, hass_config: dict) -> None:
        """Create a EnergyAssistantConfig instance."""
        self._config = {
            "energy_assistant": energy_assistant_config.copy(),
            "home_assistant": hass_config,
        }
        self._config["emhass"] = energy_assistant_config["emhass"].copy()
        del self._config["energy_assistant"]["emhass"]

    @property
    def config(self) -> dict:
        """Get the complete config."""
        return self._config

    @property
    def energy_assistant_config(self) -> dict:
        """Get the energy assistant config."""
        return self._config["energy_assistant"]

    @property
    def home_assistant_config(self) -> dict:
        """Get the home assistant config."""
        return self._config["home_assistant"]

    @property
    def emhass_config(self) -> dict:
        """Get the emhass config."""
        return self._config["emhass"]

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
