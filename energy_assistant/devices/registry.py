"""Device type registry for device data."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from energy_assistant.constants import (
    DEFAULT_NOMINAL_DURATION,
    DEFAULT_NOMINAL_POWER,
    ROOT_LOGGER_NAME,
)

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


@dataclass(frozen=True, eq=True)
class DeviceTypeId:
    """The of a device type."""

    manufacturer: str
    model: str


@dataclass
class DeviceType:
    """The device type of a device."""

    icon: str
    nominal_power: float
    nominal_duration: float
    constant: bool
    state_on_threshold: float
    state_off_threshold: float
    state_off_upper: float
    state_off_lower: float
    state_off_for: float
    trailing_zeros_for: float


class DeviceTypeRegistry:
    """The registry for device types."""

    def __init__(self) -> None:
        """Create a Device Type Registry instance."""
        self._registry: dict[DeviceTypeId, DeviceType] = {}

    def load(self, config_folder: Path) -> None:
        """Load the registry from the configuration folder."""
        for config_file in config_folder.glob("**/*/*.yaml"):
            self.load_device_type_file(config_file)

    def load_device_type_file(self, filename: Path) -> None:
        """Load a device type config file and add it to the registry."""
        with filename.open() as stream:
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError:
                LOGGER.exception("Yaml error while parsing device type file")
            except Exception:
                LOGGER.exception("error while parsing device type file")
            else:
                device_type_config = config.get("device_type")
                if device_type_config is None:
                    LOGGER.error(f"Device type config file {filename} does not contain a device_type item.")
                else:
                    manufacturer = device_type_config.get("manufacturer")
                    model = device_type_config.get("model")
                    icon = device_type_config.get("icon")
                    nominal_power = device_type_config.get("nominal_power", DEFAULT_NOMINAL_POWER)
                    nominal_duration = device_type_config.get("nominal_duration", DEFAULT_NOMINAL_DURATION)
                    constant = device_type_config.get("constant", False)
                    if model is None or manufacturer is None or icon is None:
                        LOGGER.error(f"Manufacturer or Model or Icon not set in device type config file {filename}")
                    else:
                        device_state_config = device_type_config.get("state")
                        state_on_threshold: float | None = None
                        state_on_config = device_state_config.get("state_on")
                        if state_on_config is not None:
                            state_on_threshold = state_on_config.get("threshold")

                        state_off_threshold: float = 0.0
                        state_off_upper: float | None = None
                        state_off_lower: float | None = None
                        state_off_for: float | None = None
                        state_off_config = device_state_config.get("state_off")
                        if state_off_config is not None:
                            state_off_threshold = state_off_config.get("threshold", 0.0)
                            state_off_upper = state_off_config.get("upper")
                            state_off_lower = state_off_config.get("lower")
                            state_off_for = state_off_config.get("for")
                            trailing_zeros_for = state_off_config.get("trailing_zeros_for")
                        if (
                            state_on_threshold is not None
                            and state_off_upper is not None
                            and state_off_lower is not None
                            and state_off_for is not None
                            and trailing_zeros_for is not None
                        ):
                            device_type = DeviceType(
                                icon=icon,
                                nominal_power=nominal_power,
                                nominal_duration=nominal_duration,
                                constant=constant,
                                state_on_threshold=state_on_threshold,
                                state_off_threshold=state_off_threshold,
                                state_off_upper=state_off_upper,
                                state_off_lower=state_off_lower,
                                state_off_for=state_off_for,
                                trailing_zeros_for=trailing_zeros_for,
                            )
                            self._registry[DeviceTypeId(manufacturer=manufacturer, model=model)] = device_type

    def get_device_type(self, manufacturer: str, model: str) -> DeviceType | None:
        """Get the device type for a given manufacturer and model."""
        return self._registry.get(DeviceTypeId(manufacturer=manufacturer, model=model))
