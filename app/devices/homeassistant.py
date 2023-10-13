"""Interface to the homeassistant instance."""
import logging

import requests  # type: ignore

from app import Optimizer
from app.constants import ROOT_LOGGER_NAME
from app.devices.analysis import DataBuffer
from app.devices.registry import DeviceType, DeviceTypeRegistry

from . import (
    Location,
    SessionStorage,
    State,
    StatesRepository,
    StatesSingleRepository,
    assign_if_available,
)
from .config import get_config_param
from .device import Device, DeviceWithState

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

    def get_location(self) -> Location:
        """Read the location from the Homeassistant configuration."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        response = requests.get(f"{self._url}/api/config", headers=headers)

        if response.ok:
            config = response.json()
            return Location(
                latitude=config.get("latitude"),
                longitude=config.get("longitude"),
                elevation=config.get("elevation"),
                time_zone=config.get("time_zone"),
            )
        else:
            raise Exception("Could not get location from Home Assistant.")


class HomeassistantDevice(Device):
    """A generic Homeassistant device."""

    def __init__(self, config: dict, session_storage: SessionStorage) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(config, session_storage)
        self._power_entity_id: str = get_config_param(config, "power")
        self._consumed_energy_entity_id: str = get_config_param(config, "energy")
        self._power: State | None = None
        self._consumed_energy: State | None = None
        scale = config.get("energy_scale")
        self._energy_scale: float = float(scale) if scale is not None else 1
        icon = config.get("icon")
        self._icon: str | None = str(icon)

    async def update_state(
        self, state_repository: StatesRepository, self_sufficiency: float
    ) -> None:
        """Update the own state from the states of a StatesRepository."""
        self._power = assign_if_available(
            self._power, state_repository.get_state(self._power_entity_id)
        )
        self._consumed_energy = assign_if_available(
            self._consumed_energy,
            state_repository.get_state(self._consumed_energy_entity_id),
        )
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power: float,
    ) -> None:
        """Update the device based on the current pv availablity."""
        pass

    @property
    def consumed_energy(self) -> float:
        """The consumed energy of the device."""
        energy = self._consumed_energy.numeric_value if self._consumed_energy else 0.0
        return energy * self._energy_scale

    @property
    def icon(self) -> str:
        """The icon of the device."""
        return self._icon if self._icon else "mdi-home"

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

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = HomeassistantState(
            self._consumed_energy_entity_id, str(consumed_energy)
        )


class PowerStateDevice(HomeassistantDevice, DeviceWithState):
    """A device which detects it's state by power data."""

    def __init__(
        self,
        config: dict,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a PowerStateDevie device."""
        super().__init__(config, session_storage)
        self._state: str = "unknown"
        self._power_data = DataBuffer()
        manufacturer = config.get("manufacturer")
        model = config.get("model")
        self._device_type: DeviceType | None = None
        if model is not None and manufacturer is not None:
            self._device_type = device_type_registry.get_device_type(manufacturer, model)
        if self._device_type is None:
            self._device_type = DeviceType(
                str(config.get("icon", "mdi:lightning-bolt")), 2, 0, 0, 0, 10
            )

        """
        self._state_on_threshold : float | None = None
        state_on_config = config.get("state_on")
        if state_on_config is not None:
            self._state_on_threshold = get_float_param_from_list(state_on_config, "threshold")

        self._state_off_upper : float | None = None
        self._state_off_lower : float | None = None
        self._state_off_for : float | None = None
        state_off_config = config.get("state_off")
        if state_off_config is not None:
            self._state_off_upper = get_float_param_from_list(state_off_config, "upper")
            self._state_off_lower = get_float_param_from_list(state_off_config, "lower")
            self._state_off_for = get_float_param_from_list(state_off_config, "for")
        """

    @property
    def icon(self) -> str:
        """The icon of the device."""
        if self._device_type:
            return self._device_type.icon
        else:
            return "mdi-home"

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is running."""
        return self._state

    async def update_state(
        self, state_repository: StatesRepository, self_sufficiency: float
    ) -> None:
        """Update the own state from the states of a StatesRepository."""
        old_state = self.state == "on"
        await super().update_state(state_repository, self_sufficiency)
        if self._device_type is not None:
            self._power_data.add_data_point(self.power)
            if self.state != "on" and self.power > self._device_type.state_on_threshold:
                self._state = "on"
            elif self.state != "off":
                if self.state == "on" and self.power == 0:
                    is_between = (
                        self._device_type.state_off_for > 0
                        and self._power_data.is_between(
                            self._device_type.state_off_lower,
                            self._device_type.state_off_upper,
                            self._device_type.state_off_for,
                            without_trailing_zeros=True,
                        )
                    )
                    max = self._device_type.trailing_zeros_for > 0 and self._power_data.get_max_for(
                        self._device_type.trailing_zeros_for
                    )
                    if is_between or max < 1:
                        self._state = "off"
                elif self.state == "unknown":
                    self._state = "off"
        new_state = self.state == "on"
        await super().update_session(old_state, new_state, "Power State Device")

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result: dict[str, str] = {"state": self.state}
        return result
