"""Stiebel Eltron device implementation."""
import logging

from . import Device, SessionStorage, State, StatesRepository, get_config_param
from .homeassistant import assign_if_available

STIEBEL_ELTRON_POWER = 5000


class StiebelEltronDevice(Device):
    """Stiebel Eltron heatpump. This can be either a water heating part or a heating part."""

    def __init__(self, config: dict, session_storage: SessionStorage):
        """Create a Stiebel Eltron heatpump."""
        super().__init__(get_config_param(config, "id"),
                         get_config_param(config, "name"), session_storage)
        self._consumed_energy_today: State | None = None
        self._consumed_energy_today_entity_id: str = get_config_param(
            config, "energy_today")
        self._actual_temp_entity_id: str = get_config_param(
            config, "temperature")
        self._actual_temp: State | None = None
        self._state: State | None = None
        self._store_sessions = False
        store_sessions = config.get("store_sessions")
        if store_sessions is not None and store_sessions:
            self._store_sessions = True

        self._state_entity_id: str = get_config_param(config, "state")
        self._consumed_energy_entity_id: str = get_config_param(
            config, "energy_total")
        self._consumed_energy: State | None = None
        self._icon = "mdi-heat-pump"

    async def update_state(self, state_repository:StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the Stiebel Eltron device."""
        old_state = self.state == 'on'
        self._state = assign_if_available(
            self._state, state_repository.get_state(self._state_entity_id))
        new_state = self.state == 'on'

        self._consumed_energy_today = assign_if_available(
            self._consumed_energy_today, state_repository.get_state(self._consumed_energy_today_entity_id))
        self._consumed_energy = assign_if_available(
            self._consumed_energy, state_repository.get_state(self._consumed_energy_entity_id))
        self._consumed_solar_energy.add_measurement(
            self.consumed_energy, self_sufficiency)
        self._actual_temp = assign_if_available(
            self._actual_temp, state_repository.get_state(self._actual_temp_entity_id))
        if self._store_sessions:
            if (not old_state) and new_state:
                logging.info("Start Session")
                await self.start_session("Water heating")
            elif new_state:
                logging.info("Update Session")
                await self.update_session()
            elif old_state and not new_state:
                logging.info("End Session")

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        energy = self._consumed_energy.numeric_value if self._consumed_energy else 0.0
        energy_today = self._consumed_energy_today.numeric_value if self._consumed_energy_today else 0.0
        return energy + energy_today

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is heating."""
        return self._state.value if self._state and self._state.value else "unknown"

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        if self._state is not None:
            return STIEBEL_ELTRON_POWER if self._state.value == 'on' else 0.0
        else:
            return 0.0

    @property
    def actual_temperature(self) -> float:
        """The actual temperature of the heating or water."""
        return self._actual_temp.numeric_value if self._actual_temp else 0.0

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
        self._consumed_energy = State(
            self._consumed_energy_entity_id, str(consumed_energy))
