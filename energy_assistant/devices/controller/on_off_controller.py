"""The on / off controller switches the power of a device based on the currently produced PV."""

import uuid

from energy_assistant import Optimizer
from energy_assistant.constants import POWER_HYSTERESIS
from energy_assistant.devices import OnOffState, PowerModes, StateId, StatesRepository
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.homeassistant import HOMEASSISTANT_CHANNEL


class OnOffController:
    """The on / off controller switches the power of a device based on the currently produced PV."""

    def __init__(self, device_id: uuid.UUID, output_id: str) -> None:
        """Create an on off controller instance."""
        self.switch_on_delay: float = 0
        self.switch_off_delay: float = 0
        self.nominal_power: float = 0
        self.power_mode: PowerModes = PowerModes.DEVICE_CONTROLLED
        self._device_id = device_id
        self._output_id = output_id

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        output_state = state_repository.get_state(self._output_id)
        if output_state is not None:
            state: OnOffState = OnOffState.from_str(output_state.value)
            new_state: OnOffState = state
            if self.power_mode == PowerModes.PV:
                if state == OnOffState.OFF:
                    min_power = grid_exported_power_data.get_min_for(self.switch_on_delay)
                    if min_power > self.nominal_power * (1 + POWER_HYSTERESIS):
                        new_state = OnOffState.ON
                elif state == OnOffState.OFF:
                    max_power = grid_exported_power_data.get_max_for(self.switch_off_delay)
                    if max_power > self.nominal_power * (1 - POWER_HYSTERESIS):
                        new_state = OnOffState.OFF
            elif self.power_mode == PowerModes.OPTIMIZED:
                power = optimizer.get_optimized_power(self._device_id)
                new_state = OnOffState.from_bool(power > 0)
            if state != new_state:
                state_repository.set_state(
                    StateId(
                        id=self._output_id,
                        channel=HOMEASSISTANT_CHANNEL,
                    ),
                    OnOffState.ON if new_state else OnOffState.OFF,
                )
