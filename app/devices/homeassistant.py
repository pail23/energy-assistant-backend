from abc import ABC
from datetime import datetime
import logging
from typing import Optional

import requests  # type: ignore

from . import Device, EnergyIntegrator, HomeEnergySnapshot

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
                self._states[entity_id] = State(entity_id, state.get("state"), state.get("attributes"))

    def get_state(self, entity_id:str) -> Optional[State]:
        return self._states.get(entity_id)


class DeviceConfigException(Exception):
    pass

def get_config_param(config: dict, param: str) -> str:
    """Get a config paramter as string or raise an exception if the parameter is not available."""
    result = config.get(param)
    if result is None:
        raise DeviceConfigException(f"Parameter {param} is missing in the configuration")
    else:
        return str(result)

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



STIEBEL_ELTRON_POWER = 5000
class StiebelEltronDevice(Device):
    """Stiebel Eltron heatpump. This can be either a water heating part or a heating part."""

    def __init__(self, config: dict):
        """Create a Stiebel Eltron heatpump."""
        super().__init__(get_config_param(config, "id"), get_config_param(config, "name"))
        self._consumed_energy_today : Optional[State] = None
        self._consumed_energy_today_entity_id : str = get_config_param(config, "energy_today")
        self._actual_temp_entity_id : str = get_config_param(config, "temperature")
        self._actual_temp: Optional[State] = None
        self._state :Optional[State] = None

        self._state_entity_id : str = get_config_param(config, "state")
        self._consumed_energy_entity_id : str = get_config_param(config, "energy_total")
        self._consumed_energy: Optional[State] = None
        self._icon = "mdi-heat-pump"

    def update_state(self, hass:Homeassistant, self_sufficiency: float) -> None:
        self._state =  assign_if_available(self._state, hass.get_state(self._state_entity_id))
        self._consumed_energy_today = assign_if_available(self._consumed_energy_today, hass.get_state(self._consumed_energy_today_entity_id))
        self._consumed_energy = assign_if_available(self._consumed_energy, hass.get_state(self._consumed_energy_entity_id))
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        self._actual_temp = assign_if_available(self._actual_temp, hass.get_state(self._actual_temp_entity_id))

    @property
    def consumed_energy(self)-> float:
        """Consumed energy in kWh."""
        energy =  self._consumed_energy.numeric_state if self._consumed_energy else 0.0
        energy_today =  self._consumed_energy_today.numeric_state if self._consumed_energy_today else 0.0
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
        return self._actual_temp.numeric_state if self._actual_temp else 0.0

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return self._consumed_energy is not None and self._consumed_energy.available and self._consumed_energy_today is not None and self._consumed_energy_today.available and self._actual_temp is not None and self._actual_temp.available and self._state is not None and self._state.available

class Home:
    """The home."""

    def __init__(self, config: dict) ->None:
        self._name : str = get_config_param(config, "name")
        self._solar_power_entity_id: str = get_config_param(config, "solar_power")
        self._grid_supply_power_entity_id : str = get_config_param(config, "grid_supply_power")
        self._solar_energy_entity_id : str = get_config_param(config, "solar_energy")
        self._grid_imported_energy_entity_id :str = get_config_param(config, "imported_energy")
        self._grid_exported_energy_entity_id :str = get_config_param(config, "exported_energy")

        self._solar_production_power: Optional[State] = None
        self._grid_imported_power : Optional[State] = None
        self._consumed_energy:float = 0.0

        self._grid_exported_energy : Optional[State] = None
        self._grid_imported_energy : Optional[State] = None
        self._produced_solar_energy: Optional[State] = None


        self._last_consumed_solar_energy = None
        self._consumed_solar_energy = EnergyIntegrator()
        self._energy_snapshop: Optional[HomeEnergySnapshot] = None
        self.devices = list[Device]()
        config_devices = config.get("devices")
        if config_devices is not None:
            for config_device in config_devices:
                type = config_device.get("type")
                if type == "homeassistant":
                    self.devices.append(HomeassistantDevice(config_device))
                elif type == "stiebel-eltron":
                    self.devices.append(StiebelEltronDevice(config_device))
                else:
                    logging.error(f"Unknown device type {type} in configuration")

    def add_device(self, device: Device) -> None:
        self.devices.append(device)

    @property
    def name(self) -> str:
        return self._name

    @property
    def produced_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._produced_solar_energy.numeric_state if self._produced_solar_energy else 0.0

    @property
    def grid_imported_energy(self) -> float:
        """Imported energy from the grid in kWh."""
        return self._grid_imported_energy.numeric_state if self._grid_imported_energy else 0.0

    @property
    def grid_exported_energy(self) -> float:
        """Exported energy from the grid in kWh."""
        return self._grid_exported_energy.numeric_state if self._grid_exported_energy else 0.0

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
        self._solar_production_power = assign_if_available(self._solar_production_power, hass.get_state(self._solar_power_entity_id))
        self._grid_imported_power = assign_if_available(self._grid_imported_power, hass.get_state(self._grid_supply_power_entity_id))

        self._produced_solar_energy = assign_if_available(self._produced_solar_energy, hass.get_state(self._solar_energy_entity_id))
        self._grid_imported_energy = assign_if_available(self._grid_imported_energy, hass.get_state(self._grid_imported_energy_entity_id))
        self._grid_exported_energy = assign_if_available(self._grid_exported_energy, hass.get_state(self._grid_exported_energy_entity_id))

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
        return self._solar_production_power.numeric_state if self._solar_production_power else 0.0

    @property
    def grid_supply_power(self)-> float:
        return self._grid_imported_power.numeric_state if self._grid_imported_power else 0.0

    def restore_state(self, consumed_solar_energy:float, consumed_energy:float, solar_produced_energy:float, grid_imported_energy:float, grid_exported_energy:float) -> None:
        self._consumed_solar_energy.restore_state(consumed_solar_energy)

        self._consumed_energy = consumed_energy
        self._produced_solar_energy = State(self._solar_energy_entity_id, str(solar_produced_energy))
        self._grid_imported_energy = State(self._grid_imported_energy_entity_id, str(grid_imported_energy))
        self._grid_exported_energy = State(self._grid_exported_energy_entity_id, str(grid_exported_energy))

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
