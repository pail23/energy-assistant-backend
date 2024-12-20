"""The home is the root of all devices."""

from __future__ import annotations

import logging
import uuid

from energy_assistant import Optimizer
from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.evcc import EvccDevice
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.devices.state_value import StateValue
from energy_assistant.storage.config import ConfigStorage

from . import (
    HomeEnergySnapshot,
    SessionStorage,
    State,
    StatesRepository,
    assign_if_available,
)
from .config import DeviceConfigMissingParameterError, get_config_param
from .device import Device
from .heat_pump import HeatPumpDevice, SGReadyHeatPumpDevice
from .homeassistant import HomeassistantDevice

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class HomeEnergyState:
    """Store the energy meter state of the home."""

    def __init__(self, config: dict) -> None:
        """Create a home energy state instance."""
        self._config = {}
        solar_energy_config = config.get("solar_energy")
        self._config["solar_energy"] = solar_energy_config
        if solar_energy_config is not None:
            self._solar_energy_value = StateValue(solar_energy_config)
        else:
            msg = "solar_energy"
            raise DeviceConfigMissingParameterError(msg)

        imported_energy_config = config.get("imported_energy")
        self._config["imported_energy"] = imported_energy_config
        if imported_energy_config is not None:
            self._imported_energy_value = StateValue(imported_energy_config)
        else:
            msg = "imported_energy"
            raise DeviceConfigMissingParameterError(msg)

        exported_energy_config = config.get("exported_energy")
        self._config["exported_energy"] = exported_energy_config
        if exported_energy_config is not None:
            self._exported_energy_value = StateValue(exported_energy_config)
        else:
            msg = "exported_energy"
            raise DeviceConfigMissingParameterError(msg)

        self._grid_exported_energy: State | None = None
        self._grid_imported_energy: State | None = None
        self._produced_solar_energy: State | None = None

    def create_clone(self) -> HomeEnergyState:
        """Create a home energy instance with the same configuration."""
        return HomeEnergyState(self._config)

    @property
    def produced_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._produced_solar_energy.numeric_value if self._produced_solar_energy else 0.0

    @property
    def grid_imported_energy(self) -> float:
        """Imported energy from the grid in kWh."""
        return self._grid_imported_energy.numeric_value if self._grid_imported_energy else 0.0

    @property
    def grid_exported_energy(self) -> float:
        """Exported energy from the grid in kWh."""
        return self._grid_exported_energy.numeric_value if self._grid_exported_energy else 0.0

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self.grid_imported_energy - self.grid_exported_energy + self.produced_solar_energy

    @property
    def consumed_solar_energy(self) -> float:
        """Consumed solar energy in kWh."""
        return self.produced_solar_energy - self.grid_exported_energy

    async def async_update_state(self, state_repository: StatesRepository) -> None:
        """Update the state of the home."""

        self._produced_solar_energy = assign_if_available(
            self._produced_solar_energy,
            self._solar_energy_value.evaluate(state_repository),
        )
        self._grid_imported_energy = assign_if_available(
            self._grid_imported_energy,
            self._imported_energy_value.evaluate(state_repository),
        )
        self._grid_exported_energy = assign_if_available(
            self._grid_exported_energy,
            self._exported_energy_value.evaluate(state_repository),
        )

    def get_variables(self) -> list:
        """Get all used entity variables."""
        variables = self._imported_energy_value.get_variables()
        variables.extend(self._exported_energy_value.get_variables())
        variables.extend(self._solar_energy_value.get_variables())

        return variables

    def restore_state(
        self,
        solar_produced_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
    ) -> None:
        """Restore the proviously stored state."""

        self._produced_solar_energy = State("", str(solar_produced_energy))
        self._grid_imported_energy = State("", str(grid_imported_energy))
        self._grid_exported_energy = State("", str(grid_exported_energy))


class Home:
    """The home."""

    def __init__(
        self,
        config: ConfigStorage,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a home instance."""
        self._name: str = config.home.get_param("name")

        self._home_energy_state = HomeEnergyState(config.home.as_dict())
        self._init_power_variables(config.home.as_dict())

        self.grid_exported_power_data = FloatDataBuffer()

        self._disable_device_control: bool = False
        disable_control = config.home.get("disable_device_control")
        if disable_control is not None and disable_control:
            self._disable_device_control = True

        self._energy_snapshop: HomeEnergySnapshot | None = None
        self._init_devices(config.devices.as_list(), session_storage, device_type_registry)

    def _init_devices(
        self,
        devices_config: list,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        self.devices = list[Device]()
        if devices_config is not None:
            for config_device in devices_config:
                device_type = config_device.get("type")
                self.create_device(device_type, config_device, session_storage, device_type_registry)

    def create_device(
        self,
        device_type: str,
        config: dict,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create and add a new device."""
        device: Device | None = None
        device_id = uuid.UUID(get_config_param(config, "id"))
        if device_type == "homeassistant":
            device = HomeassistantDevice(device_id, session_storage, device_type_registry)
        elif device_type == "heat-pump":
            device = HeatPumpDevice(device_id, session_storage)
        elif device_type == "sg-ready-heat-pump":
            device = SGReadyHeatPumpDevice(device_id, session_storage)
        elif device_type == "power-state-device":
            # This is deprecated and will be removed.
            device = HomeassistantDevice(device_id, session_storage, device_type_registry)
        elif device_type == "evcc":
            device = EvccDevice(device_id, session_storage)
        else:
            LOGGER.error(f"Unknown device type {device_type} in configuration")
        if device is not None:
            device.configure(config)
            self.devices.append(device)

    def _init_power_variables(self, config: dict) -> None:
        solar_power_config = config.get("solar_power")
        if solar_power_config is not None:
            self._solar_power_value = StateValue(solar_power_config)
        else:
            raise DeviceConfigMissingParameterError("solar_power")

        grid_supply_power_config = config.get("grid_supply_power")
        if grid_supply_power_config is not None:
            self._grid_imported_power_value = StateValue(grid_supply_power_config)
        else:
            raise DeviceConfigMissingParameterError("energy")

        grid_inverted: bool | None = config.get("grid_inverted")
        if grid_inverted is not None:
            if grid_inverted:
                self._grid_imported_power_value.invert_value()
            LOGGER.warning(
                "The home is configured with grid_inverted. This is deprecated and will no longer be supported.",
            )

        self._solar_production_power: State | None = None
        self._grid_imported_power: State | None = None

    def add_device(self, device: Device) -> None:
        """Add a device to the home."""
        self.devices.append(device)

    def remove_device(self, device_id: uuid.UUID) -> None:
        """Remove the device with a given id."""
        for device in self.devices:
            if device.id == device_id:
                self.devices.remove(device)
                return

    def get_device(self, id: uuid.UUID) -> Device | None:
        """Get device with the given id."""
        for device in self.devices:
            if device.id == id:
                return device
        return None

    @property
    def name(self) -> str:
        """Name of the Home."""
        return self._name

    @property
    def produced_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._home_energy_state.produced_solar_energy

    @property
    def grid_imported_energy(self) -> float:
        """Imported energy from the grid in kWh."""
        return self._home_energy_state.grid_imported_energy

    @property
    def grid_exported_energy(self) -> float:
        """Exported energy from the grid in kWh."""
        return self._home_energy_state.grid_exported_energy

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self._home_energy_state.consumed_energy

    @property
    def consumed_solar_energy(self) -> float:
        """Consumed solar energy in kWh."""
        return self._home_energy_state.consumed_solar_energy

    @property
    def home_consumption_power(self) -> float:
        """Consumpton power of the home."""
        result = self.solar_production_power - self.grid_imported_power
        if result > 0:
            return result
        return 0

    @property
    def solar_self_consumption_power(self) -> float:
        """Self consumed solar power."""
        if self.grid_imported_power < 0:
            return self.solar_production_power
        return self.solar_production_power - self.grid_imported_power

    @property
    def self_sufficiency(self) -> float:
        """Self sufficiency of the home."""
        home_consumption = self.home_consumption_power
        if home_consumption > 0:
            return min(self.solar_self_consumption_power / home_consumption, 1.0)
        return 0

    @property
    def self_consumption(self) -> float:
        """Self consumption ratio of the home."""
        solar_power = self.solar_production_power
        if solar_power > 0:
            return min(self.solar_self_consumption_power / solar_power, 1.0)
        return 0

    async def update_state(self, state_repository: StatesRepository) -> None:
        """Update the state of the home."""
        self._solar_production_power = assign_if_available(
            self._solar_production_power,
            self._solar_power_value.evaluate(state_repository),
        )
        self._grid_imported_power = assign_if_available(
            self._grid_imported_power,
            self._grid_imported_power_value.evaluate(state_repository),
        )
        await self._home_energy_state.async_update_state(state_repository)

        if self._energy_snapshop is None:
            self.set_snapshot(
                self.produced_solar_energy,
                self.grid_imported_energy,
                self.grid_exported_energy,
            )

        for device in self.devices:
            await device.update_state(state_repository, self.self_sufficiency)

    async def update_power_consumption(self, state_repository: StatesRepository, optimizer: Optimizer) -> None:
        """Update the device based on the current pv availability."""
        self.grid_exported_power_data.add_data_point(self.grid_imported_power)

        if not self._disable_device_control:
            for device in self.devices:
                await device.update_power_consumption(state_repository, optimizer, self.grid_exported_power_data)

    @property
    def icon(self) -> str:
        """The icon of the home."""
        return "mdi-home"

    @property
    def solar_production_power(self) -> float:
        """Solar production power of the home."""
        return self._solar_production_power.numeric_value if self._solar_production_power else 0.0

    @property
    def grid_imported_power(self) -> float:
        """Grid supply power of the home."""
        return self._grid_imported_power.numeric_value if self._grid_imported_power else 0.0

    def restore_state(
        self,
        solar_produced_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
    ) -> None:
        """Restore the proviously stored state."""

        self._home_energy_state.restore_state(solar_produced_energy, grid_imported_energy, grid_exported_energy)

        self.set_snapshot(
            solar_produced_energy,
            grid_imported_energy,
            grid_exported_energy,
        )

    def set_snapshot(
        self,
        solar_produced_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
    ) -> None:
        """Set the energy snapshot for the home."""
        self._energy_snapshop = HomeEnergySnapshot(
            solar_produced_energy,
            grid_imported_energy,
            grid_exported_energy,
        )

    def store_energy_snapshot(self) -> None:
        """Store the current values in the snapshot."""
        self.set_snapshot(
            self.produced_solar_energy,
            self.grid_imported_energy,
            self.grid_exported_energy,
        )
        for device in self.devices:
            device.store_energy_snapshot()

    @property
    def energy_snapshop(self) -> HomeEnergySnapshot | None:
        """The last energy snapshot of the device."""
        return self._energy_snapshop

    def get_variables(self) -> list:
        """Get all used entity variables."""
        return self._home_energy_state.get_variables()

    def create_home_energy_state_clone(self) -> HomeEnergyState:
        """Create a clone of the home energy state."""
        return self._home_energy_state.create_clone()
