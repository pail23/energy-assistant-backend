"""Handle meters which can loose their energy meter value and reset to 0. This is useful for example for meters which are resetting to 0 in case of power loss."""

import logging

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices import State

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class UtilityMeter:
    """Handle meters which can loose their energy meter value and reset to 0."""

    def __init__(self, name: str) -> None:
        """Create a utility meter instance."""
        self._last_meter_value: float = 0
        self._energy: float = 0
        self._name = name

    @property
    def name(self) -> str:
        """Name of the utility meter."""
        return self._name

    @property
    def energy(self) -> float:
        """Current energy."""
        return self._energy

    @property
    def last_meter_value(self) -> float:
        """The last measured meture value."""
        return self._last_meter_value

    def update_energy(self, energy: float) -> float:
        """Update the utility meter with a energy measurement."""
        delta: float = max(energy - self._last_meter_value, 0)
        self._last_meter_value = energy
        self._energy += delta
        return self._energy

    def update_energy_state(self, energy_state: State) -> State:
        """Update the utility meter with a energy measurement provide as State."""
        energy = energy_state.numeric_value if energy_state else 0.0
        return State(energy_state.id, str(self.update_energy(energy)), energy_state.attributes)

    def restore_last_meter_value(self, meter_value: float) -> None:
        """Restore the last meter value."""
        self._last_meter_value = meter_value
