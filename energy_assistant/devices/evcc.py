"""EVCC Devices."""

import uuid

from energy_assistant import Optimizer
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.mqtt import MQTT_CHANNEL

from . import (
    LoadInfo,
    OnOffState,
    PowerModes,
    SessionStorage,
    State,
    StateId,
    StatesRepository,
)
from .config import get_config_param
from .device import DeviceWithState


class EvccDevice(DeviceWithState):
    """Evcc load points as devices."""

    def __init__(self, device_id: uuid.UUID, session_storage: SessionStorage) -> None:
        """Create a Stiebel Eltron heatpump."""
        super().__init__(device_id, session_storage)
        self._evcc_topic: str = ""
        self._loadpoint_id: int = -1
        self._is_continous: bool = True
        self._nominal_power: float | None = None
        self._state = OnOffState.UNKNOWN
        self._power: State | None = None
        self._consumed_energy: State | None = None
        self._mode: State | None = None
        self._vehicle_soc: State | None = None
        self._max_current: State | None = None
        self._is_connected: State | None = None
        self._supported_power_modes = {
            PowerModes.DEVICE_CONTROLLED,
            PowerModes.OFF,
            PowerModes.PV,
            PowerModes.MIN_PV,
            PowerModes.FAST,
            PowerModes.OPTIMIZED,
        }
        self._utility_meter = self.add_utility_meter("energy")

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)
        self._evcc_topic = get_config_param(config, "evcc_topic")
        self._loadpoint_id = int(get_config_param(config, "load_point_id"))
        self._is_continous = bool(config.get("continuous", True))
        self._nominal_power = config.get("nominal_power")

    def get_device_topic_id(self, name: str) -> StateId:
        """Get the id of a topic of this load point."""
        return StateId(
            id=f"{self._evcc_topic}/loadpoints/{self._loadpoint_id}/{name}",
            channel=MQTT_CHANNEL,
        )

    @property
    def type(self) -> str:
        """The device type."""
        return "evcc"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the Stiebel Eltron device."""
        old_state = self.state == OnOffState.ON
        charging = state_repository.get_state(self.get_device_topic_id("charging"))
        if charging is not None:
            self._state = OnOffState.ON if charging.value == "true" else OnOffState.OFF
        else:
            self._state = OnOffState.UNKNOWN
        new_state = self.state == OnOffState.ON

        self._consumed_energy = state_repository.get_state(self.get_device_topic_id("chargeTotalImport"))
        if self.consumed_energy == 0:
            state = state_repository.get_state(self.get_device_topic_id("sessionEnergy"))
            if state is not None:
                self._consumed_energy = self._utility_meter.update_energy_state(state)
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._power = state_repository.get_state(self.get_device_topic_id("chargePower"))
        self._mode = state_repository.get_state(self.get_device_topic_id("mode"))
        self._vehicle_soc = state_repository.get_state(self.get_device_topic_id("vehicleSoc"))
        self._vehicle_capacity = state_repository.get_state(self.get_device_topic_id("vehicleCapacity"))
        self._max_current = state_repository.get_state(self.get_device_topic_id("maxCurrent"))
        self._is_connected = state_repository.get_state(self.get_device_topic_id("connected"))

        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        await self.update_session(old_state, new_state, "EVCC")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        new_state = ""
        if self.power_mode == PowerModes.OFF:
            new_state = "off"
        elif self.power_mode == PowerModes.PV:
            new_state = "pv"
        elif self.power_mode == PowerModes.MIN_PV:
            new_state = "minpv"
        elif self.power_mode == PowerModes.FAST:
            new_state = "now"
        elif self.power_mode == PowerModes.OPTIMIZED:
            # TODO: Implement Optimized with emhass
            new_state = "pv"
        if new_state != self._mode:
            state_repository.set_state(self.get_device_topic_id("mode/set"), new_state)

    @property
    def evcc_mqtt_subscription_topic(self) -> str:
        """Get the evvc base topic for the subscription."""
        return f"{self._evcc_topic}/#"

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self._consumed_energy.numeric_value if self._consumed_energy else 0.0

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is loading."""
        return self._state

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        return self._power.numeric_value if self._power else 0.0

    @property
    def mode(self) -> str:
        """Current PV mode of the device."""
        return self._mode.value if self._mode else "unknown"

    @property
    def vehicle_soc(self) -> float:
        """State of Charge of the connected vehicle."""
        return self._vehicle_soc.numeric_value if self._vehicle_soc else 0.0

    @property
    def vehicle_capacity(self) -> float:
        """Capacity of the connected vehicle."""
        return self._vehicle_capacity.numeric_value if self._vehicle_capacity else 0.0

    @property
    def icon(self) -> str:
        """Icon of the device."""
        return "mdi-car-electric"

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return True

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore the previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = State(self.get_device_topic_id("chargeTotalImport").id, str(consumed_energy))

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result: dict[str, str] = {
            **super().attributes,
            "pv_mode": self.mode,
        }
        if self._vehicle_soc is not None:
            result["vehicle_soc"] = f"{round(self.vehicle_soc)} %"
        return result

    def get_load_info(self) -> LoadInfo | None:
        """Get the current deferrable load info."""
        if (
            self.state == OnOffState.ON
            and self._is_connected is not None
            and self._max_current is not None
            and self._is_connected.value == "true"
        ):
            remaining_energy = (1 - self.vehicle_soc / 100) * self.vehicle_capacity * 1000
            if remaining_energy > 0:
                power: float = (
                    self._nominal_power if self._nominal_power is not None else (self._max_current.numeric_value * 230)
                )  # TODO: Multiply with active phases
                return LoadInfo(
                    device_id=self.id,
                    nominal_power=power,
                    duration=remaining_energy / power * 3600,
                    is_continous=self._is_continous,
                    is_deferrable=self.power_mode == PowerModes.OPTIMIZED,
                )
        return None
