"""Interface to the homeassistant instance."""
import logging

import requests  # type: ignore

from energy_assistant import Optimizer
from energy_assistant.constants import (
    DEFAULT_NOMINAL_DURATION,
    DEFAULT_NOMINAL_POWER,
    POWER_HYSTERESIS,
    ROOT_LOGGER_NAME,
)
from energy_assistant.devices.analysis import DataBuffer
from energy_assistant.devices.registry import DeviceType, DeviceTypeRegistry
from energy_assistant.devices.state_value import StateValue

from . import (
    DeferrableLoadInfo,
    Location,
    PowerModes,
    SessionStorage,
    State,
    StateId,
    StatesRepository,
    StatesSingleRepository,
    assign_if_available,
)
from .config import DeviceConfigException, get_config_param
from .device import DeviceWithState

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)
UNAVAILABLE = "unavailable"

HOMEASSISTANT_CHANNEL = "ha"


class HomeassistantState(State):
    """Abstract base class for states."""

    def __init__(self, id: str, value: str, attributes: dict = {}) -> None:
        """Create a State instance."""
        super().__init__(id, value, attributes)

        if value == UNAVAILABLE:
            self._available = False
        else:
            self._available = True

    @property
    def name(self) -> str:
        """The name of the State."""
        if self._attributes is not None:
            return str(self._attributes.get("friendly_name"))
        return self._id

    @property
    def unit(self) -> str:
        """Unit of the state."""
        if self._attributes is not None:
            return str(self._attributes.get("unit_of_measurement"))
        return ""


class Homeassistant(StatesSingleRepository):
    """Home assistant proxy."""

    def __init__(self, url: str, token: str, demo_mode: bool) -> None:
        """Create an instance of the Homeassistant class."""
        super().__init__(HOMEASSISTANT_CHANNEL)
        self._url = url
        self._token = token
        self._demo_mode = demo_mode is not None and demo_mode

    @property
    def url(self) -> str:
        """URL of the home assistant instance."""
        return self._url

    @property
    def token(self) -> str:
        """Token of the home assistant instance."""
        return self._token

    def read_states(self) -> None:
        """Read the states from the homeassistant instance."""
        if self._demo_mode:
            self._read_states["sensor.solaredge_i1_ac_power"] = HomeassistantState(
                "sensor.solaredge_i1_ac_power", "10000"
            )
            self._read_states["sensor.solaredge_m1_ac_power"] = HomeassistantState(
                "sensor.solaredge_m1_ac_power", "6000"
            )
            self._read_states["sensor.keba_charge_power"] = HomeassistantState(
                "sensor.keba_charge_power", "2500"
            )
            self._read_states["sensor.tumbler_power"] = HomeassistantState(
                "sensor.tumbler_power", "600"
            )
            self._read_states["sensor.officedesk_power"] = HomeassistantState(
                "sensor.officedesk_power", "40"
            )
            self._read_states["sensor.rack_power"] = HomeassistantState("sensor.rack_power", "80")
        else:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "content-type": "application/json",
            }
            try:
                response = requests.get(f"{self._url}/api/states", headers=headers)

                if response.ok:
                    states = response.json()
                    self._read_states.clear()
                    for state in states:
                        entity_id = state.get("entity_id")
                        self._read_states[entity_id] = HomeassistantState(
                            entity_id, state.get("state"), state.get("attributes")
                        )
                    self._template_states = None

            except Exception:
                LOGGER.exception("Exception during homeassistant update_states: ")

    def write_states(self) -> None:
        """Send the changed states to hass."""
        if not self._demo_mode:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "content-type": "application/json",
            }
            try:
                for id, state in self._write_states.items():
                    if id.startswith("number"):
                        data = {"entity_id": id, "value": state.value}
                        response = requests.post(
                            f"{self._url}/api/services/number/set_value",
                            headers=headers,
                            json=data,
                        )
                        if not response.ok:
                            LOGGER.error("State update in hass failed")
                    elif id.startswith("switch"):
                        data = {"entity_id": id}
                        response = requests.post(
                            f"{self._url}/api/services/switch/turn_{state.value}",
                            headers=headers,
                            json=data,
                        )
                        if not response.ok:
                            LOGGER.error("Turn switch update in hass failed")
                    elif id.startswith("sensor"):
                        sensor_data: dict = {
                            "state": state.value,
                            "attributes": state.attributes,
                        }
                        response = requests.post(
                            f"{self._url}/api/states/{id}",
                            headers=headers,
                            json=sensor_data,
                        )
                        if not response.ok:
                            LOGGER.error(f"State update for {id} in hass failed")
                    else:
                        LOGGER.error(f"Writing to id {id} is not yet implemented.")
            except Exception as ex:
                LOGGER.error("Exception during homeassistant update_states: ", ex)
            self._write_states.clear()

    def get_config(self) -> dict:
        """Read the Homeassistant configuration."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        response = requests.get(f"{self._url}/api/config", headers=headers)

        if response.ok:
            return response.json()
        else:
            raise Exception("Could not get location from Home Assistant.")

    def get_location(self) -> Location:
        """Read the location from the Homeassistant configuration."""
        config = self.get_config()

        return Location(
            latitude=config.get("latitude", ""),
            longitude=config.get("longitude", ""),
            elevation=config.get("elevation", ""),
            time_zone=config.get("time_zone", ""),
        )


class HomeassistantDevice(DeviceWithState):
    """A generic Homeassistant device."""

    def __init__(
        self,
        config: dict,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(config, session_storage)
        self._power_entity_id: str = get_config_param(config, "power")
        energy_config = config.get("energy")
        if energy_config is not None:
            self._consumed_energy_value = StateValue(energy_config)
        else:
            raise DeviceConfigException("Parameter energy is missing in the configuration")

        energy_scale: float | None = config.get("energy_scale")
        if energy_scale is not None:
            self._consumed_energy_value.set_scale(energy_scale)
            LOGGER.warn(
                f"Homeassistant device with id {self.id} is configured with energy_scale. This is deprecated and will no longer be supported."
            )

        self._output_id: str | None = config.get("output")
        self._nominal_power: float | None = None
        self._nominal_duration: float | None = None
        self._is_constant: bool | None = None

        self._power: State | None = None
        self._consumed_energy: State | None = None
        self._output_state: State | None = None
        self._icon: str = str(config.get("icon", "mdi-home"))

        if self._output_id is not None:
            self._supported_power_modes.append(PowerModes.PV)
            self.supported_power_modes.append(PowerModes.OPTIMIZED)

        self._power_data = DataBuffer()
        manufacturer = config.get("manufacturer")
        model = config.get("model")
        self._device_type: DeviceType | None = None
        if model is not None and manufacturer is not None:
            self._device_type = device_type_registry.get_device_type(manufacturer, model)
            self._nominal_power = config.get(
                "nominal_power", self._device_type.nominal_power if self._device_type else None
            )
            self._nominal_duration = config.get(
                "nominal_duration",
                self._device_type.nominal_duration if self._device_type else None,
            )
            self._is_constant = config.get(
                "constant", self._device_type.constant if self._device_type else None
            )
        else:
            self._nominal_power = config.get("nominal_power")
            self._nominal_duration = config.get("nominal_duration")
            self._is_constant = config.get("constant")

        state_detection: dict = config.get("state", {})
        if self._device_type is None and state_detection:
            state_on = state_detection.get("state_on", {})
            state_off = state_detection.get("state_off", {})
            self._device_type = DeviceType(
                str(config.get("icon", "mdi:lightning-bolt")),
                self._nominal_power if self._nominal_power is not None else DEFAULT_NOMINAL_POWER,
                self._nominal_duration
                if self._nominal_duration is not None
                else DEFAULT_NOMINAL_DURATION,
                self._is_constant if self._is_constant is not None else False,
                state_on.get("threshold", 2),
                state_off.get("threshold", 0),
                state_off.get("upper", 0),
                state_off.get("lower", 0),
                state_off.get("for", 0),
                state_off.get("trailing_zeros_for", 10),
            )
        self._state: str
        if self.has_state:
            self._state = "unknown"
        else:
            self._state = "not supported"

    @property
    def type(self) -> str:
        """The device type."""
        return "homeassistant"

    async def update_state(
        self, state_repository: StatesRepository, self_sufficiency: float
    ) -> None:
        """Update the own state from the states of a StatesRepository."""
        if self._output_id is not None:
            self._output_state = assign_if_available(
                self._output_state, state_repository.get_state(self._output_id)
            )
        else:
            self._output_state = None
        self._power = assign_if_available(
            self._power, state_repository.get_state(self._power_entity_id)
        )
        self._consumed_energy = assign_if_available(
            self._consumed_energy,
            self._consumed_energy_value.evaluate(state_repository),
        )
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        if self.has_state:
            old_state = self.state == "on"
            if self._device_type is not None:
                self._power_data.add_data_point(self.power)
                if self.state != "on" and self.power > self._device_type.state_on_threshold:
                    self._state = "on"
                elif self.state != "off":
                    if self.state == "on" and self.power <= self._device_type.state_off_threshold:
                        is_between = (
                            self._device_type.state_off_for > 0
                            and self._power_data.is_between(
                                self._device_type.state_off_lower,
                                self._device_type.state_off_upper,
                                self._device_type.state_off_for,
                                without_trailing_zeros=True,
                            )
                        )
                        max = (
                            self._device_type.trailing_zeros_for > 0
                            and self._power_data.get_max_for(self._device_type.trailing_zeros_for)
                        )
                        if is_between or max <= self._device_type.state_off_threshold:
                            self._state = "off"
                    elif self.state == "unknown":
                        self._state = "off"
            new_state = self.state == "on"
            await super().update_session(old_state, new_state, "Power State Device")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: DataBuffer,
    ) -> None:
        """Update the device based on the current pv availablity."""
        if self._output_id is not None:
            state: bool = (
                self._output_state.value == "on" if self._output_state is not None else False
            )
            new_state = state
            if self.power_mode == PowerModes.PV:
                avg_300 = grid_exported_power_data.get_average_for(300)
                if avg_300 > self.nominal_power * (1 + POWER_HYSTERESIS):
                    new_state = True
                elif avg_300 < self.nominal_power * (1 - POWER_HYSTERESIS):
                    new_state = False
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

    def get_deferrable_load_info(self) -> DeferrableLoadInfo | None:
        """Get the current deferrable load info."""
        if (
            self.power_mode == PowerModes.OPTIMIZED
            and self._nominal_power is not None
            and self._nominal_duration is not None
        ):
            return DeferrableLoadInfo(
                device_id=self.id,
                nominal_power=self._nominal_power,
                deferrable_hours=round(self._nominal_duration / 3600),
                is_continous=False,
                is_constant=self._is_constant if self._is_constant is not None else False,
            )
        return None
