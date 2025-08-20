"""State management for EMHASS optimizer."""

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from energy_assistant.devices import StateId, StatesRepository
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import HOMEASSISTANT_CHANNEL

if TYPE_CHECKING:
    from .config import EmhassConfig


class StateManager:
    """Handle state repository updates and device management."""

    def __init__(self, config: "EmhassConfig") -> None:
        """Initialize state manager."""
        self._config = config
        self._optimzed_devices: list = []

    def set_optimized_devices(self, devices: list) -> None:
        """Set the optimized devices."""
        self._optimzed_devices = devices

    def update_repository_states(
        self,
        home: Home,
        state_repository: StatesRepository,
        no_var_loads_buffer: FloatDataBuffer,
        get_forecast_value_func: Callable[[str], float],
    ) -> None:
        """Calculate the power of the non variable/non controllable loads."""
        power = home.home_consumption_power
        for device in home.devices:
            if device.power_controllable:
                power = power - device.power
        if power < 0:
            power = 0.0
        no_var_loads_buffer.add_data_point(power)

        attributes = {
            "unit_of_measurement": "W",
            "state_class": "measurement",
            "device_class": "power",
        }

        state_repository.set_state(
            StateId(id=self._config.power_no_var_loads_id, channel=HOMEASSISTANT_CHANNEL),
            str(power),
            attributes,
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._config.hass_entity_prefix}_p_pv", channel=HOMEASSISTANT_CHANNEL),
            str(get_forecast_value_func("P_PV")),
            attributes,
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._config.hass_entity_prefix}_p_consumption", channel=HOMEASSISTANT_CHANNEL),
            str(get_forecast_value_func("P_Load")),
            attributes,
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._config.hass_entity_prefix}_home_consumption", channel=HOMEASSISTANT_CHANNEL),
            str(home.home_consumption_power),
            attributes,
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._config.hass_entity_prefix}_self_sufficiency", channel=HOMEASSISTANT_CHANNEL),
            str(round(home.self_sufficiency * 100)),
            {
                "unit_of_measurement": "%",
                "state_class": "measurement",
            },
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._config.hass_entity_prefix}_self_consumption", channel=HOMEASSISTANT_CHANNEL),
            str(round(home.self_consumption * 100)),
            {
                "unit_of_measurement": "%",
                "state_class": "measurement",
            },
        )

    def get_optimized_power(self, device_id: uuid.UUID, get_forecast_value_func: Callable[[str], float]) -> float:
        """Get the optimized power budget for a given device."""
        for i, deferrable_load_info in enumerate(self._optimzed_devices):
            if deferrable_load_info.device_id == device_id:
                column_name = f"P_deferrable{i}"
                return get_forecast_value_func(column_name)
        return -1

    def has_deferrable_load(self, device_id: uuid.UUID) -> bool:
        """Check if device has deferrable load."""
        return any(deferrable_load_info.device_id == device_id for deferrable_load_info in self._optimzed_devices)
