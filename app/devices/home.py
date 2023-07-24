"""The home is the root of all devices."""

import logging

from . import Device, HomeEnergySnapshot, get_config_param
from .homeassistant import (
    Homeassistant,
    HomeassistantDevice,
    State,
    assign_if_available,
)
from .stiebel_eltron import StiebelEltronDevice


class Home:
    """The home."""

    def __init__(self, config: dict) ->None:
        """Create a home instance."""
        self._name : str = get_config_param(config, "name")
        self._solar_power_entity_id: str = get_config_param(config, "solar_power")
        self._grid_supply_power_entity_id : str = get_config_param(config, "grid_supply_power")
        self._solar_energy_entity_id : str = get_config_param(config, "solar_energy")
        self._grid_imported_energy_entity_id :str = get_config_param(config, "imported_energy")
        self._grid_exported_energy_entity_id :str = get_config_param(config, "exported_energy")

        self._solar_production_power: State | None = None
        self._grid_imported_power : State | None = None
        self._consumed_energy:float = 0.0
        self._consumed_solar_energy: float = 0.0

        self._grid_exported_energy : State | None = None
        self._grid_imported_energy : State | None = None
        self._produced_solar_energy: State | None = None

        self._energy_snapshop: HomeEnergySnapshot | None = None
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
        """Add a device to the home."""
        self.devices.append(device)

    @property
    def name(self) -> str:
        """Name of the Home."""
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
        return self._consumed_solar_energy

    @property
    def home_consumption_power(self) -> float:
        """Consumpton power of the home."""
        result = self.solar_production_power - self.grid_supply_power
        if result > 0:
            return result
        else:
                return 0

    @property
    def solar_self_consumption_power(self) -> float:
        """Self consumption power of the home."""
        if self.grid_supply_power < 0:
            return self.solar_production_power
        else:
            return self.solar_production_power - self.grid_supply_power


    @property
    def self_sufficiency(self) -> float:
        """Self sufficiency of the home."""
        hc = self.home_consumption_power
        if hc > 0:
            return min(self.solar_self_consumption_power / hc, 1.0)
        else:
            return 0


    def update_state_from_hass(self, hass:Homeassistant) -> None:
        """Update the state of the home."""
        self._solar_production_power = assign_if_available(self._solar_production_power, hass.get_state(self._solar_power_entity_id))
        self._grid_imported_power = assign_if_available(self._grid_imported_power, hass.get_state(self._grid_supply_power_entity_id))

        self._produced_solar_energy = assign_if_available(self._produced_solar_energy, hass.get_state(self._solar_energy_entity_id))
        self._grid_imported_energy = assign_if_available(self._grid_imported_energy, hass.get_state(self._grid_imported_energy_entity_id))
        self._grid_exported_energy = assign_if_available(self._grid_exported_energy, hass.get_state(self._grid_exported_energy_entity_id))

        self._consumed_energy = self.grid_imported_energy - self.grid_exported_energy +  self.produced_solar_energy
        self._consumed_solar_energy =  self.produced_solar_energy - self.grid_exported_energy

        if self._energy_snapshop is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy, self.produced_solar_energy, self.grid_imported_energy, self.grid_exported_energy)

        for device in self.devices:
            if isinstance(device, HomeassistantDevice) or isinstance(device, StiebelEltronDevice):
                device.update_state(hass, self.self_sufficiency)


    @property
    def icon(self) -> str:
        """The icon of the home."""
        return "mdi-home"

    @property
    def solar_production_power(self)-> float:
        """Solar production power of the home."""
        return self._solar_production_power.numeric_state if self._solar_production_power else 0.0

    @property
    def grid_supply_power(self)-> float:
        """Grid supply power of the home."""
        return self._grid_imported_power.numeric_state if self._grid_imported_power else 0.0

    def restore_state(self, consumed_solar_energy:float, consumed_energy:float, solar_produced_energy:float, grid_imported_energy:float, grid_exported_energy:float) -> None:
        """Restore the proviously stored state."""
        self._consumed_solar_energy = consumed_solar_energy
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
    def energy_snapshop(self) -> HomeEnergySnapshot | None:
        """The last energy snapshot of the device."""
        return self._energy_snapshop
