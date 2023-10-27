"""Handle meters which can loose their energy meter value and reset to 0. This is useful for example for meters which are reseting to 0 in case of power loss."""
import logging

from app.constants import ROOT_LOGGER_NAME
from app.devices import State

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class UtilityMeter:
    """Handle meters which can loose their energy meter value and reset to 0."""

    def __init__(self) -> None:
        """Create a utility meter instance."""
        self._last_meter_value: float = 0
        self._energy: float = 0

    @property
    def energy(self) -> float:
        """Current energy."""
        return self._energy

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
