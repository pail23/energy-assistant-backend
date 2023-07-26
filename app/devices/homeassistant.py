"""Interface to the homeassistant instance."""
import logging

import requests  # type: ignore

from . import (
    Device,
    SessionStorage,
    State,
    StatesRepository,
    assign_if_available,
    get_config_param,
)

UNAVAILABLE = "unavailable"


class HomeassistantState(State):
    """Abstract base class for states."""

    def __init__(self, id:str, value:str, attributes:dict = {}) -> None:
        """Create a State instance."""
        super().__init__(id, value)
        self._attributes = attributes

        if value==UNAVAILABLE:
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
        return None




class Homeassistant(StatesRepository):
    """Home assistant proxy."""

    def __init__(self, url:str, token:str, demo_mode: bool) -> None:
        """Create an instance of the Homeassistant class."""
        super().__init__()
        self._url = url
        self._token = token
        self._demo_mode = demo_mode is not None and demo_mode


    def read_states(self) -> None:
        """Read the states from the homeassistant instance."""
        if self._demo_mode:
            self._read_states["sensor.solaredge_i1_ac_power"] = HomeassistantState("sensor.solaredge_i1_ac_power", "10000")
            self._read_states["sensor.solaredge_m1_ac_power"] = HomeassistantState("sensor.solaredge_m1_ac_power", "6000")
            self._read_states["sensor.keba_charge_power"] = HomeassistantState("sensor.keba_charge_power", "2500")
            self._read_states["sensor.tumbler_power"] = HomeassistantState("sensor.tumbler_power", "600")
            self._read_states["sensor.officedesk_power"] = HomeassistantState("sensor.officedesk_power", "40")
            self._read_states["sensor.rack_power"] = HomeassistantState("sensor.rack_power", "80")
        else:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "content-type": "application/json",
            }
            try:
                response = requests.get(
                    f"{self._url}/api/states", headers=headers)

                if response.ok:
                    states = response.json()
                    self._read_states.clear()
                    for state in states:
                        entity_id = state.get("entity_id")
                        self._read_states[entity_id] = HomeassistantState(entity_id, state.get("state"), state.get("attributes"))

            except Exception as ex:
                logging.error("Exception during homeassistant update_states: ", ex)

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
                            f"{self._url}/api/services/number/set_value", headers=headers, json=data)
                        if not response.ok:
                            logging.error("State update in hass failed")
                    else:
                        logging.error(f"Writing to id {id} is not yet implemented.")
            except Exception as ex:
                logging.error("Exception during homeassistant update_states: ", ex)

class HomeassistantDevice(Device):
    """A generic Homeassistant device."""

    def __init__(self, config: dict, session_storage: SessionStorage) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(get_config_param(config, "id"), get_config_param(config, "name"), session_storage)
        self._power_entity_id : str = get_config_param(config, "power")
        self._consumed_energy_entity_id : str = get_config_param(config, "energy")
        self._power: State | None= None
        self._consumed_energy: State | None  = None
        scale = config.get("energy_scale")
        self._energy_scale : float = float(scale) if scale is not None else 1
        icon = config.get("icon")
        self._icon : str = str(icon) if icon is not None else "mdi-home"

    async def update_state(self, state_repository:StatesRepository, self_sufficiency: float) -> None:
        """Update the own state from the states of a StatesRepository."""
        self._power = assign_if_available(self._power, state_repository.get_state(self._power_entity_id))
        self._consumed_energy = assign_if_available(self._consumed_energy, state_repository.get_state(self._consumed_energy_entity_id))
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)

    async def update_power_consumption(self, state_repository: StatesRepository, grid_exported_power: float) -> None:
        """"Update the device based on the current pv availablity."""
        pass

    @property
    def consumed_energy(self) -> float:
        """The consumed energy of the device."""
        energy = self._consumed_energy.numeric_value if self._consumed_energy else 0.0
        return energy * self._energy_scale

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
        return self._consumed_energy  is not None and self._consumed_energy.available and self._power is not None and self._power.available

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = HomeassistantState(self._consumed_energy_entity_id, str(consumed_energy))
