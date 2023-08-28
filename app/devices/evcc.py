"""EVCC Devices."""
from app.mqtt import MQTT_CHANNEL

from . import SessionStorage, State, StateId, StatesRepository
from .config import get_config_param
from .device import Device, DeviceWithState


class EvccDevice(Device, DeviceWithState):
    """Evcc load points as devices."""

    def __init__(self, config: dict, session_storage: SessionStorage):
        """Create a Stiebel Eltron heatpump."""
        super().__init__(config, session_storage)
        self._evcc_topic: str = get_config_param(
            config, "evcc_topic")
        self._loadpoint_id: int = int(get_config_param(config, "load_point_id"))
        self._state = "unknown"
        self._power : State | None= None
        self._consumed_energy : State | None= None
        self._mode : State | None= None


    def get_device_topic_id(self, name: str) -> StateId:
        """Get the id of a topic of this load point."""
        return StateId(id=f"{self._evcc_topic}/loadpoints/{self._loadpoint_id}/{name}", channel=MQTT_CHANNEL)

    async def update_state(self, state_repository:StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the Stiebel Eltron device."""
        old_state = self.state == 'on'
        charging = state_repository.get_state(self.get_device_topic_id("charging"))
        if charging is not None:
            self._state = 'on' if charging.value == "true" else 'off'
        else:
            self._state = 'unknown'
        new_state = self.state == 'on'

        self._consumed_energy = state_repository.get_state(self.get_device_topic_id("chargeTotalImport"))
        self._power = state_repository.get_state(self.get_device_topic_id("chargePower"))
        self._mode = state_repository.get_state(self.get_device_topic_id("mode"))

        await super().update_session(old_state, new_state, "EVCC")


    async def update_power_consumption(self, state_repository: StatesRepository, grid_exported_power: float) -> None:
        """"Update the device based on the current pv availablity."""
        pass

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
        self._consumed_energy = State(
            self.get_device_topic_id("chargeTotalImport").id, str(consumed_energy))

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result : dict[str, str]= {
            "state": self.state,
            "pv_mode": self.mode
        }
        return result