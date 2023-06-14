from abc import ABC
from datetime import datetime
from typing import Optional

import requests

from . import Device, EnergyIntegrator, HomeEnergySnapshot

UNAVAILABLE = "unavailable"

class State(ABC):
    """Abstract base class for states."""

    def __init__(self, entity_id:str, state:str, attributes:dict) -> None:
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
        return self._state

    @property
    def numeric_state(self) -> Optional[float]:
        try:
            return float(self._state)
        except ValueError:
            return None

    @property
    def unit(self) -> str:
        if self._attributes is not None:
            return str(self._attributes.get("unit_of_measurement"))
        return None


class NumericState(State):
    def __init__(self, entity_id:str, state:str, attributes:dict):
        super().__init__(entity_id, state, attributes)


class StrState(State):
    """String State from Home Assistant."""

    def __init__(self, entity_id:str, state:str, attributes:dict):
        """Create a string state instance."""
        super().__init__(entity_id, state, attributes)



class Homeassistant:
    """Home assistant proxy."""

    def __init__(self, url:str, token:str) -> None:
        self._url = url
        self._states = dict[str, State]()
        self._token = token


    def update_states(self) -> None:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        time_stamp = datetime.now().timestamp()
        response = requests.get(
            f"{self._url}/api/states", headers=headers)
        datetime.now().timestamp() - time_stamp
        if response.ok:
            states = response.json()
            self._states = dict[str, State]()
            for state in states:
                entity_id = state.get("entity_id")
                self._states[entity_id] = NumericState(entity_id, state.get("state"), state.get("attributes")) if entity_id.startswith("sensor.") else StrState(entity_id, state.get("state"), state.get("attributes"))

    def get_state(self, entity_id:str) -> Optional[NumericState]:
        state = self._states.get(entity_id)
        if state and isinstance(state, NumericState):
            return state
        else:
            return None


    def get_str_state(self, entity_id:str) -> Optional[StrState]:
        state = self._states.get(entity_id)
        if state and isinstance(state, StrState):
            return state
        else:
            return None


class HomeassistantDevice(Device):
    """A generic Homeassistant device."""

    def __init__(self, name:str, power_entity_id:str, consumed_energy_entity_id:str, icon:str,  energy_scale: float = 1) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(name)
        self._power_entity_id = power_entity_id
        self._consumed_energy_entity_id = consumed_energy_entity_id
        self._power: Optional[NumericState]= None
        self._consumed_energy: Optional[NumericState]  = None
        self._energy_scale = energy_scale
        self._icon = icon

    def update_state(self, hass:Homeassistant, self_sufficiency: float) -> None:
        state = hass.get_state(self._power_entity_id)
        if state and state.available:
            self._power = state
        state = hass.get_state(self._consumed_energy_entity_id)
        if state and state.available:
            self._consumed_energy = state
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)

    @property
    def consumed_energy(self) -> float:
        energy = self._consumed_energy.numeric_state if self._consumed_energy is not None and self._consumed_energy.numeric_state is not None else 0.0
        return energy * self._energy_scale

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def power(self) -> float:
        """The current power used by the device."""
        return self._power.numeric_state if self._power and self._power.numeric_state else 0.0



STIEBEL_ELTRON_POWER = 5000
class StiebelEltronDevice(Device):
    """Stiebel Eltron heatpump. This can be either a water heating part or a heating part."""

    def __init__(self, name:str, state_entity_id:str, consumed_energy_entity_id:str, consumed_energy_today_entity_id:str, actual_temp_entity_id:str):
        """Create a Stiebel Eltron heatpump."""
        super().__init__(name)
        self._consumed_energy_today : Optional[NumericState] = None
        self._consumed_energy_today_entity_id = consumed_energy_today_entity_id
        self._actual_temp_entity_id = actual_temp_entity_id
        self._actual_temp: Optional[NumericState] = None
        self._state :Optional[StrState] = None

        self._state_entity_id = state_entity_id
        self._consumed_energy_entity_id = consumed_energy_entity_id
        self._consumed_energy: Optional[NumericState] = None
        self._icon = "mdi-heat-pump"

    def update_state(self, hass:Homeassistant, self_sufficiency: float) -> None:
        self._state = hass.get_str_state(self._state_entity_id)
        self._consumed_energy_today = hass.get_state(self._consumed_energy_today_entity_id)
        self._consumed_energy = hass.get_state(self._consumed_energy_entity_id)
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._actual_temp = hass.get_state(self._actual_temp_entity_id)

    @property
    def consumed_energy(self)-> float:
        """Consumed energy in kWh."""
        energy =  self._consumed_energy.numeric_state if self._consumed_energy and self._consumed_energy.numeric_state else 0.0
        energy_today =  self._consumed_energy_today.numeric_state if self._consumed_energy_today and self._consumed_energy_today.numeric_state else 0.0
        return energy + energy_today

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is heating."""
        return self._state.state if self._state and self._state.state else "unknown"

    @property
    def power(self) -> float:
        """Current power consumption of the device."""
        if self._state is not None:
            return STIEBEL_ELTRON_POWER if self._state.state == 'on' else 0.0
        else:
            return 0.0

    @property
    def actual_temperature(self) -> float:
        return self._actual_temp.numeric_state if self._actual_temp and self._actual_temp.numeric_state else 0.0

    @property
    def icon(self) -> str:
        return self._icon

class Home:
    """The home."""

    def __init__(self, name:str, solar_power_entity_id:str, grid_supply_power_entity_id:str, solar_energy_entity_id:str, grid_import_energy_entity_id:str, grid_export_energy_entity_id:str) ->None:
        self._name = name
        self._solar_power_entity_id = solar_power_entity_id
        self._grid_supply_power_entity_id = grid_supply_power_entity_id
        self._solar_energy_entity_id = solar_energy_entity_id
        self._grid_imported_energy_entity_id = grid_import_energy_entity_id
        self._grid_exported_energy_entity_id = grid_export_energy_entity_id

        self._solar_production_power: Optional[NumericState] = None
        self._grid_imported_power : Optional[NumericState] = None
        self._consumed_energy:float = 0.0

        self._grid_exported_energy : Optional[NumericState] = None
        self._grid_imported_energy : Optional[NumericState] = None
        self._produced_solar_energy: Optional[NumericState] = None


        self._last_consumed_solar_energy = None
        self._consumed_solar_energy = EnergyIntegrator()
        self._energy_snapshop: Optional[HomeEnergySnapshot] = None
        self.devices = list[Device]()


    def add_device(self, device: Device) -> None:
        self.devices.append(device)

    @property
    def name(self) -> str:
        return self._name

    @property
    def produced_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._produced_solar_energy.numeric_state if self._produced_solar_energy and self._produced_solar_energy.numeric_state else 0.0

    @property
    def grid_imported_energy(self) -> float:
        """Imported energy from the grid in kWh."""
        return self._grid_imported_energy.numeric_state if self._grid_imported_energy and self._grid_imported_energy.numeric_state else 0.0

    @property
    def grid_exported_energy(self) -> float:
        """Exported energy from the grid in kWh."""
        return self._grid_exported_energy.numeric_state if self._grid_exported_energy and self._grid_exported_energy.numeric_state else 0.0

    @property
    def consumed_energy(self) ->float:
        """Consumed energy in kWh."""
        return self._consumed_energy

    @property
    def consumed_solar_energy(self) -> float:
        """Consumed solar energy in kWh."""
        return self._consumed_solar_energy.consumed_solar_energy

    @property
    def home_consumption_power(self) -> float:
        result = self.solar_production_power - self.grid_supply_power
        if result > 0:
            return result
        else:
            return 0

    @property
    def solar_self_consumption_power(self) -> float:
        if self.grid_supply_power < 0:
            return self.solar_production_power
        else:
            return self.solar_production_power - self.grid_supply_power


    @property
    def self_sufficiency(self) -> float:
        hc = self.home_consumption_power
        if hc > 0:
            return min(self.solar_self_consumption_power / hc, 1.0)
        else:
            return 0


    def update_state_from_hass(self, hass:Homeassistant) -> None:
        self._solar_production_power = hass.get_state(self._solar_power_entity_id)
        self._grid_imported_power = hass.get_state(self._grid_supply_power_entity_id)


        self._produced_solar_energy = hass.get_state(self._solar_energy_entity_id)
        self._grid_imported_energy = hass.get_state(self._grid_imported_energy_entity_id)
        self._grid_exported_energy = hass.get_state(self._grid_exported_energy_entity_id)
        self._consumed_energy = self.grid_imported_energy - self.grid_exported_energy +  self.produced_solar_energy
        self._consumed_solar_energy.add_measurement(self._consumed_energy, self.self_sufficiency)

        if self._energy_snapshop is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy, self.produced_solar_energy, self.grid_imported_energy, self.grid_exported_energy)

        for device in self.devices:
            if isinstance(device, HomeassistantDevice) or isinstance(device, StiebelEltronDevice):
                device.update_state(hass, self.self_sufficiency)


    @property
    def icon(self) -> str:
        return "mdi-home"

    @property
    def solar_production_power(self)-> float:
        return self._solar_production_power.numeric_state if self._solar_production_power and self._solar_production_power.numeric_state else 0.0

    @property
    def grid_supply_power(self)-> float:
        return self._grid_imported_power.numeric_state if self._grid_imported_power and self._grid_imported_power.numeric_state else 0.0

    def restore_state(self, consumed_solar_energy:float, consumed_energy:float, solar_produced_energy:float, grid_imported_energy:float, grid_exported_energy:float) -> None:
        self._consumed_solar_energy.restore_state(consumed_solar_energy)
        self.set_snapshot(consumed_solar_energy, consumed_energy, solar_produced_energy, grid_imported_energy, grid_exported_energy)

    def set_snapshot(self, consumed_solar_energy: float, consumed_energy: float, solar_produced_energy: float, grid_imported_energy: float, grid_exported_energy: float) -> None:
        """Set the energy snapshot for the home."""
        self._energy_snapshop = HomeEnergySnapshot(consumed_solar_energy, consumed_energy, solar_produced_energy, grid_imported_energy, grid_exported_energy)

    def store_energy_snapshot(self) -> None:
        """Store the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy, self.produced_solar_energy, self.grid_imported_energy, self.grid_exported_energy)
        for device in self.devices:
            device.store_energy_snapshot()

    @property
    def energy_snapshop(self) -> Optional[HomeEnergySnapshot]:
        """The last energy snapshot of the device."""
        return self._energy_snapshop
