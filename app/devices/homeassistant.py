from abc import ABC
import logging
from typing import Optional

import requests  # type: ignore

from . import Device, get_config_param

UNAVAILABLE = "unavailable"

class State(ABC):
    """Abstract base class for states."""

    def __init__(self, entity_id:str, state:str, attributes:dict = {}) -> None:
        """Create a State instance."""
        self._attributes = attributes
        self._entity_id = entity_id
        self._state = state
        if state==UNAVAILABLE:
            self._available = False
        else:
            self._available = True


    @property
    def name(self) -> str:
        if self._attributes is not None:
            return str(self._attributes.get("friendly_name"))
        return self._entity_id

    @property
    def entity_id(self) -> str:
        return self._entity_id

    @property
    def available(self) -> bool:
        """Availability of the state."""
        return self._available

    @property
    def state(self) -> str:
        """State of the state as string."""
        return self._state

    @property
    def numeric_state(self) -> float:
        """Numeric state of the state."""
        try:
            return float(self._state)
        except ValueError:
            return 0.0

    @property
    def unit(self) -> str:
        """Unit of the state."""
        if self._attributes is not None:
            return str(self._attributes.get("unit_of_measurement"))
        return None

def assign_if_available(old_state: Optional[State], new_state: Optional[State]) -> Optional[State]:
    """Return new state in case the state is available, otherwise old state."""
    if new_state and new_state.available:
        return new_state
    else:
        return old_state


class Homeassistant:
    """Home assistant proxy."""

    def __init__(self, url:str, token:str, demo_mode: bool) -> None:
        self._url = url
        self._states = dict[str, State]()
        self._token = token
        self._demo_mode = demo_mode is not None and demo_mode


    def update_states(self) -> None:
        if self._demo_mode:
            self._states["sensor.solaredge_i1_ac_power"] = State("sensor.solaredge_i1_ac_power", "10000")
            self._states["sensor.solaredge_m1_ac_power"] = State("sensor.solaredge_m1_ac_power", "6000")
            self._states["sensor.keba_charge_power"] = State("sensor.keba_charge_power", "2500")
            self._states["sensor.tumbler_power"] = State("sensor.tumbler_power", "600")
            self._states["sensor.officedesk_power"] = State("sensor.officedesk_power", "40")
            self._states["sensor.rack_power"] = State("sensor.rack_power", "80")
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
                    self._states = dict[str, State]()
                    for state in states:
                        entity_id = state.get("entity_id")
                        self._states[entity_id] = State(entity_id, state.get("state"), state.get("attributes"))

            except Exception as ex:
                logging.error("Exception during homeassistant update_states: ", ex)

    def get_state(self, entity_id:str) -> Optional[State]:
        return self._states.get(entity_id)



class HomeassistantDevice(Device):
    """A generic Homeassistant device."""

    def __init__(self, config: dict) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(get_config_param(config, "id"), get_config_param(config, "name"))
        self._power_entity_id : str = get_config_param(config, "power")
        self._consumed_energy_entity_id : str = get_config_param(config, "energy")
        self._power: Optional[State]= None
        self._consumed_energy: Optional[State]  = None
        scale = config.get("energy_scale")
        self._energy_scale : float = float(scale) if scale is not None else 1
        icon = config.get("icon")
        self._icon : str = str(icon) if icon is not None else "mdi-home"

    def update_state(self, hass:Homeassistant, self_sufficiency: float) -> None:
        self._power = assign_if_available(self._power, hass.get_state(self._power_entity_id))
        self._consumed_energy = assign_if_available(self._consumed_energy, hass.get_state(self._consumed_energy_entity_id))
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)

    @property
    def consumed_energy(self) -> float:
        energy = self._consumed_energy.numeric_state if self._consumed_energy else 0.0
        return energy * self._energy_scale

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def power(self) -> float:
        """The current power used by the device."""
        return self._power.numeric_state if self._power else 0.0

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return self._consumed_energy  is not None and self._consumed_energy.available and self._power is not None and self._power.available

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = State(self._consumed_energy_entity_id, str(consumed_energy))
