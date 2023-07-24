"""Stiebel Eltron device implementation."""
from . import Device, get_config_param
from .homeassistant import Homeassistant, State, assign_if_available

STIEBEL_ELTRON_POWER = 5000
class StiebelEltronDevice(Device):
    """Stiebel Eltron heatpump. This can be either a water heating part or a heating part."""

    def __init__(self, config: dict):
        """Create a Stiebel Eltron heatpump."""
        super().__init__(get_config_param(config, "id"), get_config_param(config, "name"))
        self._consumed_energy_today : State | None = None
        self._consumed_energy_today_entity_id : str = get_config_param(config, "energy_today")
        self._actual_temp_entity_id : str = get_config_param(config, "temperature")
        self._actual_temp: State | None = None
        self._state :State | None = None

        self._state_entity_id : str = get_config_param(config, "state")
        self._consumed_energy_entity_id : str = get_config_param(config, "energy_total")
        self._consumed_energy: State | None = None
        self._icon = "mdi-heat-pump"

    def update_state(self, hass:Homeassistant, self_sufficiency: float) -> None:
        """Update the state of the Stiebel Eltron device."""
        self._state =  assign_if_available(self._state, hass.get_state(self._state_entity_id))
        self._consumed_energy_today = assign_if_available(self._consumed_energy_today, hass.get_state(self._consumed_energy_today_entity_id))
        self._consumed_energy = assign_if_available(self._consumed_energy, hass.get_state(self._consumed_energy_entity_id))
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._actual_temp = assign_if_available(self._actual_temp, hass.get_state(self._actual_temp_entity_id))

    @property
    def consumed_energy(self)-> float:
        """Consumed energy in kWh."""
        energy =  self._consumed_energy.numeric_state if self._consumed_energy else 0.0
        energy_today =  self._consumed_energy_today.numeric_state if self._consumed_energy_today else 0.0
        return energy + energy_today

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is heating."""
        return self._state.state if self._state and self._state.state else "unknown"

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        if self._state is not None:
            return STIEBEL_ELTRON_POWER if self._state.state == 'on' else 0.0
        else:
            return 0.0

    @property
    def actual_temperature(self) -> float:
        """The actual temperature of the heating or water."""
        return self._actual_temp.numeric_state if self._actual_temp else 0.0

    @property
    def icon(self) -> str:
        """Icon of the device."""
        return self._icon

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return self._consumed_energy is not None and self._consumed_energy.available and self._consumed_energy_today is not None and self._consumed_energy_today.available and self._actual_temp is not None and self._actual_temp.available and self._state is not None and self._state.available

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore the previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = State(self._consumed_energy_entity_id, str(consumed_energy))