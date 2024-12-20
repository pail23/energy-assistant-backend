"""Heat pump device implementation."""

import uuid

from energy_assistant import Optimizer
from energy_assistant.constants import POWER_HYSTERESIS
from energy_assistant.devices.device import DeviceWithState
from energy_assistant.devices.state_value import StateValue

from . import (
    LoadInfo,
    OnOffState,
    PowerModes,
    SessionStorage,
    State,
    StateId,
    StatesRepository,
)
from .analysis import FloatDataBuffer
from .config import DeviceConfigMissingParameterError, get_config_param
from .homeassistant import HOMEASSISTANT_CHANNEL, assign_if_available

DEFAULT_NOMINAL_POWER = 5000


def numeric_value(value: str | None) -> float | None:
    """Convert into a number."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class HeatPumpDevice(DeviceWithState):
    """Stiebel Eltron heatpump. This can be either a water heating part or a heating part."""

    def __init__(self, device_id: uuid.UUID, session_storage: SessionStorage) -> None:
        """Create a Stiebel Eltron heatpump."""
        super().__init__(device_id, session_storage)
        self._actual_temp: State | None = None
        self._actual_temp_entity_id: str = ""
        self._comfort_target_temperature_entity_id: str | None = None
        self._state_entity_id: str = ""
        self._state: State | None = None
        self._consumed_energy: State | None = None
        self._icon = "mdi-heat-pump"
        self._nominal_power: float = DEFAULT_NOMINAL_POWER
        self._target_temperature_normal: float | None = None
        self._target_temperature_pv: float | None = None
        self._consumed_energy_value: StateValue | None = None

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)
        energy_config = config.get("energy")
        if energy_config is not None:
            self._consumed_energy_value = StateValue(energy_config)
        else:
            msg = "energy"
            raise DeviceConfigMissingParameterError(msg)
        self._actual_temp_entity_id = get_config_param(config, "temperature")
        self._nominal_power = config.get("nominal_power", DEFAULT_NOMINAL_POWER)
        self._comfort_target_temperature_entity_id = config.get("comfort_target_temperature")
        self._target_temperature_normal = numeric_value(config.get("target_temperature_normal"))
        self._target_temperature_pv = numeric_value(config.get("target_temperatrure_pv"))
        if (
            self._target_temperature_normal is not None
            and self._target_temperature_pv is not None
            and self._comfort_target_temperature_entity_id is not None
        ):
            self._supported_power_modes.add(PowerModes.PV)
            self._supported_power_modes.add(PowerModes.OPTIMIZED)

        self._state_entity_id = get_config_param(config, "state")

    @property
    def type(self) -> str:
        """The device type."""
        return "heat-pump"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the Stiebel Eltron device."""
        old_state = self.state == "on"
        self._state = assign_if_available(self._state, state_repository.get_state(self._state_entity_id))
        new_state = self.state == "on"

        self._consumed_energy = assign_if_available(
            self._consumed_energy,
            self._consumed_energy_value.evaluate(state_repository) if self._consumed_energy_value is not None else None,
        )
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._actual_temp = assign_if_available(
            self._actual_temp,
            state_repository.get_state(self._actual_temp_entity_id),
        )

        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        await self.update_session(old_state, new_state, "Water heater")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        if (
            self._target_temperature_normal is not None
            and self._target_temperature_pv is not None
            and self._comfort_target_temperature_entity_id is not None
        ):
            current_target_temperature = state_repository.get_state(self._comfort_target_temperature_entity_id)
            if current_target_temperature is not None:
                target_temperature: float = current_target_temperature.numeric_value
                if self.power_mode == PowerModes.PV:
                    if self.state == "off":
                        avg_300 = grid_exported_power_data.get_average_for(300)
                        if avg_300 > self.requested_additional_power * (1 + POWER_HYSTERESIS):
                            target_temperature = self._target_temperature_pv
                        elif avg_300 < self.requested_additional_power * (1 - POWER_HYSTERESIS):
                            target_temperature = self._target_temperature_normal
                elif self.power_mode == PowerModes.OPTIMIZED:
                    target_temperature = self._get_temperature_for_optimized(optimizer, target_temperature)
                if target_temperature != current_target_temperature.numeric_value:
                    state_repository.set_state(
                        StateId(
                            id=self._comfort_target_temperature_entity_id,
                            channel=HOMEASSISTANT_CHANNEL,
                        ),
                        str(target_temperature),
                    )

    def _get_temperature_for_optimized(self, optimizer: Optimizer, current_target_temperature: float) -> float:
        if (
            self.state == "off"
            and self._target_temperature_normal is not None
            and self._target_temperature_pv is not None
        ):
            power = optimizer.get_optimized_power(self._id)
            if power > 0:
                return self._target_temperature_pv
            return self._target_temperature_normal
        return current_target_temperature

    def get_load_info(self) -> LoadInfo | None:
        """Get the current deferrable load info."""
        if self.power_mode == PowerModes.OPTIMIZED:
            return LoadInfo(
                device_id=self.id,
                nominal_power=self._nominal_power,
                duration=1800,  # 0.5h -> TODO: make this configurable
                is_continous=False,
                is_deferrable=True,
            )
        return None

    @property
    def requested_additional_power(self) -> float:
        """How much power the device could consume in pv mode."""
        # TODO: Consider the actual temperature
        return self._nominal_power if self.state == "off" else 0.0

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self._consumed_energy.numeric_value if self._consumed_energy else 0.0

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is heating."""
        return self._state.value if self._state and self._state.value else "unknown"

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        if self._state is not None:
            return self._nominal_power if self._state.value == "on" else 0.0
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
        return (
            self._consumed_energy is not None
            and self._consumed_energy.available
            and self._actual_temp is not None
            and self._actual_temp.available
            and self._state is not None
            and self._state.available
        )

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore the previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = State("", str(consumed_energy))

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result: dict[str, str] = {
            **super().attributes,
            "actual_temperature": f"{self.actual_temperature} °C",
        }
        return result


class SubHeatPump(DeviceWithState):
    """The heating or the water heating part of the heat pump."""

    def __init__(self, device_id: uuid.UUID, session_storage: SessionStorage, name: str) -> None:
        """Create a sub heat pump instance."""
        super().__init__(device_id, session_storage)

        self._actual_temp_entity_id: str = ""
        self._actual_temp: State | None = None
        self._state: State | None = None
        self._state_entity_id: str = ""
        self._consumed_energy: State | None = None
        self._consumed_energy_value: StateValue | None = None

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        sub_device_config = {**config, "name": self.name, "id": uuid.uuid4()}
        super().configure(sub_device_config)
        energy_config = config.get("energy")
        if energy_config is not None:
            self._consumed_energy_value = StateValue(energy_config)
        else:
            msg = "energy"
            raise DeviceConfigMissingParameterError(msg)
        self._actual_temp_entity_id = get_config_param(config, "temperature")
        self._state_entity_id = get_config_param(config, "state")

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the SGReady Heatpump."""

        # old_state = self.state == OnOffState.ON
        self._state = assign_if_available(self._state, state_repository.get_state(self._state_entity_id))
        # new_state = self.state == OnOffState.ON
        self._consumed_energy = assign_if_available(
            self._consumed_energy,
            self._consumed_energy_value.evaluate(state_repository) if self._consumed_energy_value is not None else None,
        )
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._actual_temp = assign_if_available(
            self._actual_temp,
            state_repository.get_state(self._actual_temp_entity_id),
        )

        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        # TODO: implement session tracking for sub devices
        # await self.update_session(old_state, new_state, self._name)

    @property
    def actual_temperature(self) -> float:
        """The actual temperature of the heating or water."""
        return self._actual_temp.numeric_value if self._actual_temp else 0.0

    @property
    def state(self) -> OnOffState:
        """The state of the device. The state is `on` in case the device is heating."""
        return OnOffState.from_str(self._state.value) if self._state and self._state.value else OnOffState.UNKNOWN

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return (
            self._consumed_energy is not None
            and self._consumed_energy.available
            and self._actual_temp is not None
            and self._actual_temp.available
            and self._state is not None
            and self._state.available
        )

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self._consumed_energy.numeric_value if self._consumed_energy else 0.0

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        raise NotImplementedError

    @property
    def type(self) -> str:
        """The device type."""
        return "sg-ready-heat-pump"

    @property
    def icon(self) -> str:
        """The icon of the device."""
        return "mdi-heat-pump"

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        raise NotImplementedError

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result: dict[str, str] = {
            **super().attributes,
            "actual_temperature": f"{self.actual_temperature} °C",
        }
        return result


class SGReadyHeatPumpDevice(DeviceWithState):
    """SG Ready heatpump, supporting water and heating temperature."""

    def __init__(self, device_id: uuid.UUID, session_storage: SessionStorage) -> None:
        """Create a SG Ready heatpump."""
        super().__init__(device_id, session_storage)

        self._heating = SubHeatPump(device_id, session_storage, "heating")

        self._water_heating = SubHeatPump(device_id, session_storage, "water_heating")

        self._nominal_power: float = DEFAULT_NOMINAL_POWER
        self._sg_ready_switch_entity_id: str | None = None

        self._icon = "mdi-heat-pump"

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)
        if self._heating is not None:
            self._heating.configure(config.get("heating", {}))
        if self._water_heating is not None:
            self._water_heating.configure(config.get("water", {}))
        self._nominal_power = config.get("nominal_power", DEFAULT_NOMINAL_POWER)
        self._sg_ready_switch_entity_id = config.get("sg_ready")
        if self._sg_ready_switch_entity_id is not None:
            self._supported_power_modes.add(PowerModes.PV)
            self._supported_power_modes.add(PowerModes.OPTIMIZED)

    @property
    def type(self) -> str:
        """The device type."""
        return "sg-ready-heat-pump"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the SGReady heatpump."""

        old_state = self.state == OnOffState.ON

        if self._heating is not None:
            await self._heating.update_state(state_repository, self_sufficiency)

        if self._water_heating is not None:
            await self._water_heating.update_state(state_repository, self_sufficiency)

        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)

        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        await self.update_session(old_state, self.state == OnOffState.ON, "Heat pump")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        if self._sg_ready_switch_entity_id is not None:
            current_sg_ready_state = state_repository.get_state(self._sg_ready_switch_entity_id)
            if current_sg_ready_state is not None:
                sg_ready_state = OnOffState.from_str(current_sg_ready_state.value)
                if self.power_mode == PowerModes.PV:
                    if self.state == OnOffState.OFF:
                        avg_300 = grid_exported_power_data.get_average_for(300)
                        if avg_300 > self.requested_additional_power * (1 + POWER_HYSTERESIS):
                            sg_ready_state = OnOffState.ON
                        elif avg_300 < self.requested_additional_power * (1 - POWER_HYSTERESIS):
                            sg_ready_state = OnOffState.OFF
                elif self.power_mode == PowerModes.OPTIMIZED:
                    sg_ready_state = self._get_state_for_optimized(
                        optimizer,
                        OnOffState.from_str(current_sg_ready_state.value),
                    )
                if sg_ready_state != OnOffState.from_str(current_sg_ready_state.value):
                    state_repository.set_state(
                        StateId(
                            id=self._sg_ready_switch_entity_id,
                            channel=HOMEASSISTANT_CHANNEL,
                        ),
                        str(sg_ready_state),
                    )

    @property
    def state(self) -> OnOffState:
        """State of the device."""
        if self._heating is not None and self._heating.state == OnOffState.ON:
            return OnOffState.ON
        if self._water_heating is not None and self._water_heating.state == OnOffState.ON:
            return OnOffState.ON
        return OnOffState.OFF

    def get_load_info(self) -> LoadInfo | None:
        """Get the current deferrable load info."""
        if self.power_mode == PowerModes.OPTIMIZED:
            return LoadInfo(
                device_id=self.id,
                nominal_power=self._nominal_power,
                duration=1800,  # 0.5h -> TODO: make this configurable
                is_continous=False,
                is_deferrable=True,
            )
        return None

    def _get_state_for_optimized(self, optimizer: Optimizer, current_state: OnOffState) -> OnOffState:
        if self.state == OnOffState.OFF:
            power = optimizer.get_optimized_power(self._id)
            if power > 0:
                return OnOffState.ON
            return OnOffState.ON
        return current_state

    @property
    def requested_additional_power(self) -> float:
        """How much power the device could consume in pv mode."""
        # TODO: Consider the actual temperature
        return self._nominal_power if self.state == "off" else 0.0

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        result: float = 0.0
        if self._heating is not None:
            result += self._heating.consumed_energy
        if self._water_heating is not None:
            result += self._water_heating.consumed_energy
        return result

    @property
    def consumed_solar_energy(self) -> float:
        """Consumed solar energy in kWh."""
        result: float = 0.0
        if self._heating is not None:
            result += self._heating.consumed_solar_energy
        if self._water_heating is not None:
            result += self._water_heating.consumed_solar_energy
        return result

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        return self._nominal_power if self.state == OnOffState.ON else 0.0

    @property
    def icon(self) -> str:
        """Icon of the device."""
        return self._icon

    @property
    def available(self) -> bool:
        """Is the device available?."""
        if self._heating is not None and self._heating.available:
            return True
        return self._water_heating is not None and self._water_heating.available

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore the previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        heating_attributes = (
            {"heating_" + k: v for k, v in self._heating.attributes.items()} if self._heating is not None else {}
        )
        del heating_attributes["heating_state"]
        water_heating_attributes = (
            {"water_heating_" + k: v for k, v in self._water_heating.attributes.items()}
            if self._water_heating is not None
            else {}
        )
        del water_heating_attributes["water_heating_state"]

        heatpump_state = str(OnOffState.OFF)
        if self._heating is not None and self._heating.state == OnOffState.ON:
            heatpump_state = "Heating"
        elif self._water_heating is not None and self._water_heating.state == OnOffState.ON:
            heatpump_state = "Water heating"
        return {
            **super().attributes,
            **heating_attributes,
            **water_heating_attributes,
            "heatpump_state": heatpump_state,
        }
