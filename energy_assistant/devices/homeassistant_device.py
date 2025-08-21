"""Generic Home Assistant device."""

import logging
import uuid
from datetime import UTC, datetime

from energy_assistant.constants import (
    DEFAULT_NOMINAL_DURATION,
    DEFAULT_NOMINAL_POWER,
    POWER_HYSTERESIS,
    ROOT_LOGGER_NAME,
)
from energy_assistant.devices import (
    LoadInfo,
    OnOffState,
    PowerModes,
    SessionStorage,
    State,
    StateId,
    StatesRepository,
    assign_if_available,
)
from energy_assistant.devices.analysis import FloatDataBuffer, OnOffDataBuffer
from energy_assistant.devices.config import get_config_param
from energy_assistant.devices.device import DeviceWithState
from energy_assistant.devices.homeassistant import HOMEASSISTANT_CHANNEL, HomeassistantState, convert_to_kwh
from energy_assistant.devices.registry import DeviceType, DeviceTypeRegistry
from energy_assistant.optimizer_base import Optimizer

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class ReadOnlyHomeassistantDevice(DeviceWithState):
    """A generic Home Assistant device without control ability."""

    def __init__(
        self,
        device_id: uuid.UUID,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a generic Home Assistant device."""
        super().__init__(device_id, session_storage)
        self._device_type_registry = device_type_registry
        self._nominal_power: float | None = None
        self._nominal_duration: float | None = None
        self._is_constant: bool = False

        self._power_entity_id: str = ""
        self._power: State | None = None
        self._consumed_energy: State | None = None
        self._icon: str = "mdi-home"
        self._power_data = FloatDataBuffer()

        self._state: str = OnOffState.UNKNOWN
        self._consumed_energy_entity_id: str = ""
        self._device_type: DeviceType | None = None

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)

        self._power_entity_id = get_config_param(config, "power")
        self._consumed_energy_entity_id = get_config_param(config, "energy")

        self._icon = str(config.get("icon", "mdi-home"))

        manufacturer = config.get("manufacturer")
        model = config.get("model")

        if model is not None and manufacturer is not None:
            self._device_type = self._device_type_registry.get_device_type(manufacturer, model)
            self._nominal_power = config.get(
                "nominal_power",
                self._device_type.nominal_power if self._device_type else None,
            )
            self._nominal_duration = config.get(
                "nominal_duration",
                self._device_type.nominal_duration if self._device_type else None,
            )
            self._is_constant = config.get("constant", self._device_type.constant if self._device_type else False)
        else:
            nominal_power = config.get("nominal_power")
            if nominal_power is not None:
                self._nominal_power = float(nominal_power)
            self._nominal_duration = config.get("nominal_duration")
            self._is_constant = config.get("constant", False)

        if self._device_type is None and (state_detection := config.get("state", {})):
            state_on = state_detection.get("state_on", {})
            state_off = state_detection.get("state_off", {})
            self._device_type = DeviceType(
                str(config.get("icon", "mdi:lightning-bolt")),
                self._nominal_power if self._nominal_power is not None else DEFAULT_NOMINAL_POWER,
                (self._nominal_duration if self._nominal_duration is not None else DEFAULT_NOMINAL_DURATION),
                self._is_constant,
                state_on.get("threshold", 2),
                state_off.get("threshold", 0),
                state_off.get("upper", 2.0),
                state_off.get("lower", 0),
                state_off.get("for", 0),
                state_off.get("trailing_zeros_for", 10),
            )

    def get_default_config(self) -> dict:
        """Get the default configuration for the device."""
        return {
            "nominal_power": 300.0,
            "nominal_duration": 60.0,
        }

    @property
    def type(self) -> str:
        """The device type."""
        return "readonly-homeassistant"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the own state from the states of a StatesRepository."""
        self._power = assign_if_available(self._power, state_repository.get_state(self._power_entity_id))
        self._consumed_energy = assign_if_available(
            self._consumed_energy, convert_to_kwh(state_repository.get_state(self._consumed_energy_entity_id))
        )

        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        if self.has_state:
            await self.check_state()

    async def check_state(self) -> None:
        """Check the state of the device and update it if necessary."""
        old_state = self.state == OnOffState.ON
        if self._device_type is not None:
            self._power_data.add_data_point(self.power)
            if self.state != OnOffState.ON and self.power > self._device_type.state_on_threshold:
                self._state = OnOffState.ON
            elif self.state != OnOffState.OFF:
                if self.state == OnOffState.ON and self.power <= self._device_type.state_off_threshold:
                    is_between = self._device_type.state_off_for > 0 and self._power_data.is_between(
                        self._device_type.state_off_lower,
                        self._device_type.state_off_upper,
                        self._device_type.state_off_for,
                        without_trailing_zeros=True,
                    )
                    max_value = self._device_type.trailing_zeros_for > 0 and self._power_data.get_max_for(
                        self._device_type.trailing_zeros_for,
                    )
                    if is_between or max_value <= self._device_type.state_off_threshold:
                        self._state = OnOffState.OFF
                elif self.state == OnOffState.UNKNOWN:
                    self._state = OnOffState.OFF
        new_state = self.state == OnOffState.ON
        await super().update_session(old_state, new_state, "Power State Device")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""

    @property
    def consumed_energy(self) -> float:
        """The consumed energy of the device."""
        return self._consumed_energy.numeric_value if self._consumed_energy is not None else 0.0

    @property
    def icon(self) -> str:
        """The icon of the device."""
        return self._icon

    @property
    def power(self) -> float:
        """The current power used by the device."""
        return self._power.numeric_value if self._power else 0.0

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return (
            self._consumed_energy is not None
            and self._consumed_energy.available
            and self._power is not None
            and self._power.available
        )

    @property
    def nominal_power(self) -> float:
        """The nominal power of the device."""
        return self._nominal_power if self._nominal_power is not None else DEFAULT_NOMINAL_POWER

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = HomeassistantState("", str(consumed_energy))

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is running."""
        return self._state

    @property
    def has_state(self) -> bool:
        """Has this device a state."""
        return self._device_type is not None

    def get_load_info(self) -> LoadInfo | None:
        """Get the current deferrable load info."""
        if self._nominal_power is not None and self._nominal_duration is not None:
            if self.power_mode == PowerModes.OPTIMIZED:
                return LoadInfo(
                    device_id=self.id,
                    nominal_power=self._nominal_power,
                    duration=self._nominal_duration,
                    is_continous=False,
                    is_constant=self._is_constant,
                    is_deferrable=True,
                )

            if self.state == OnOffState.ON:
                return LoadInfo(
                    device_id=self.id,
                    nominal_power=self._nominal_power,
                    duration=self._nominal_duration - self.session_duration,
                    is_continous=False,
                    is_constant=self._is_constant,
                    is_deferrable=False,
                )

        return None


class HomeassistantDevice(ReadOnlyHomeassistantDevice):
    """A generic Home Assistant device which can be controlled."""

    def __init__(
        self,
        device_id: uuid.UUID,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a generic Home Assistant device."""
        super().__init__(device_id, session_storage, device_type_registry)
        self._output_state: State | None = None
        self._output_id: str | None = None
        self._output_states = OnOffDataBuffer()
        self._max_on_per_day: float = 24 * 60 * 60  # seconds
        self._min_on_duration: float = 0.0
        self._switch_off_delay: float = 0.0
        self._switch_on_delay: float = 0.0

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)
        self._output_id = config.get("output")

        self._supported_power_modes.add(PowerModes.PV)
        self._supported_power_modes.add(PowerModes.OPTIMIZED)

        self._max_on_per_day = config.get("max_on_per_day", 24 * 60 * 60)  # seconds
        self._min_on_duration = config.get("min_on_duration", 60.0)  # seconds
        self._switch_off_delay = config.get("switch_off_delay", 300.0)  # seconds
        self._switch_on_delay = config.get("switch_on_delay", 300.0)  # seconds

    def get_default_config(self) -> dict:
        """Get the default configuration for the device."""
        return {
            "switch_on_delay": 300.0,
            "switch_off_delay": 300.0,
            "min_on_duration": 60.0,
            "max_on_per_day": 24 * 60 * 60,  # seconds
        }

    @property
    def type(self) -> str:
        """The device type."""
        return "homeassistant"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the own state from the states of a StatesRepository."""
        if self._output_id is not None:
            self._output_state = assign_if_available(self._output_state, state_repository.get_state(self._output_id))
        else:
            self._output_state = None
        await super().update_state(state_repository, self_sufficiency)

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        if self._output_id is None:
            return
        state: bool = self._output_state.value == "on" if self._output_state is not None else False
        new_state = state
        if self.power_mode == PowerModes.PV:
            midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            if state:
                max_grid_power = grid_exported_power_data.get_max_for(self._switch_off_delay)
                if (
                    max_grid_power < self.nominal_power * (1 - POWER_HYSTERESIS)
                    and self._output_states.duration_in_state(True).total_seconds() > self._min_on_duration
                ) or self._output_states.total_duration_in_state_since(
                    True, midnight
                ).total_seconds() > self._max_on_per_day:
                    new_state = False
            else:
                # If the device is off, we check if the average power is below the nominal power
                # to turn it on again.
                min_grid_power = grid_exported_power_data.get_min_for(self._switch_on_delay)
                if (
                    min_grid_power > self.nominal_power * (1 + POWER_HYSTERESIS)
                    and self._output_states.total_duration_in_state_since(True, midnight).total_seconds()
                    < self._max_on_per_day
                ):
                    new_state = True

        elif self.power_mode == PowerModes.OPTIMIZED:
            power = optimizer.get_optimized_power(self._id)
            new_state = power > 0
        if state != new_state:
            state_repository.set_state(
                StateId(
                    id=self._output_id,
                    channel=HOMEASSISTANT_CHANNEL,
                ),
                "on" if new_state else "off",
            )
            self._output_states.add_data_point(new_state)
