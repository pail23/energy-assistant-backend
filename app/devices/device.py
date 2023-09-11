"""Device base class for all devices."""
from abc import ABC, abstractmethod
import logging
import uuid

from app import Optimizer

from . import (
    EnergyIntegrator,
    EnergySnapshot,
    PowerModes,
    SessionStorage,
    StatesRepository,
)
from .config import get_config_param


class Device(ABC):
    """A device which tracks energy consumption."""

    def __init__(self, config: dict, session_storage: SessionStorage) -> None:
        """Create a device."""
        self._name = get_config_param(config, "name")
        self._id = uuid.UUID(get_config_param(config, "id"))
        self._consumed_solar_energy = EnergyIntegrator()
        self._energy_snapshot: EnergySnapshot | None = None
        self.session_storage: SessionStorage = session_storage
        self.current_session : int | None = None
        self._supported_power_modes : list[PowerModes] = [PowerModes.DEVICE_CONTROLLED]
        self._power_mode : PowerModes = PowerModes.DEVICE_CONTROLLED
        self._store_sessions = False
        store_sessions = config.get("store_sessions")
        if store_sessions is not None and store_sessions:
            self._store_sessions = True



    @property
    def name(self) -> str:
        """The name of the device."""
        return self._name


    @property
    def supported_power_modes(self) -> list[PowerModes]:
        """Returns the supported power modes for the device."""
        return self._supported_power_modes

    @property
    def power_mode(self) -> PowerModes:
        """The power mode of the device."""
        return self._power_mode

    @property
    def power_controllable(self) -> bool:
        """The power mode of the device."""
        return not(len(self._supported_power_modes) == 1 and self._supported_power_modes[0] == PowerModes.DEVICE_CONTROLLED)

    def set_power_mode(self, power_mode: PowerModes) -> None:
        """Set the power mode of the device."""
        self._power_mode = power_mode

    @property
    def id(self) -> uuid.UUID:
        """The id of the device."""
        return self._id

    @property
    def consumed_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._consumed_solar_energy.consumed_solar_energy if self._consumed_solar_energy.consumed_solar_energy is not None else 0.0

    @property
    @abstractmethod
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        pass

    @property
    @abstractmethod
    def power(self) -> float:
        """Current consumed power."""
        pass

    @property
    @abstractmethod
    def available(self) -> float:
        """Is the device availabe?."""
        pass

    @property
    @abstractmethod
    def icon(self) -> str:
        """Icon for the device."""
        pass

    @abstractmethod
    async def update_power_consumption(self, state_repository: StatesRepository, optimizer: Optimizer, grid_exported_power: float) -> None:
        """"Update the device based on the current pv availablity."""
        pass

    @abstractmethod
    async def update_state(self, state_repository:StatesRepository, self_sufficiency: float) -> None:
        """Update the state of the device."""
        pass

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state of the device."""
        self._consumed_solar_energy.restore_state(consumed_solar_energy, consumed_energy)
        self.set_snapshot(consumed_solar_energy, consumed_energy)

    def set_snapshot(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Set the snapshot values."""
        self._energy_snapshot = EnergySnapshot(consumed_solar_energy, consumed_energy)

    @property
    def energy_snapshot(self)-> EnergySnapshot | None:
        """The last energy snapshot of the device."""
        return self._energy_snapshot

    def store_energy_snapshot(self) -> None:
        """Store the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

    async def start_session(self, text: str) -> None:
        """Start a session."""
        self.current_session = await self.session_storage.start_session(self._id, text,self.consumed_solar_energy, self.consumed_energy)

    async def update_session(self, old_state: bool, new_state: bool, text: str) -> None:
        """Update the session log."""
        if self._store_sessions:
            if new_state:
                if old_state:
                    if self.current_session is not None:
                        await self.session_storage.update_session(self.current_session, self.consumed_solar_energy, self.consumed_energy)
                else:
                    logging.info("Start Session")
                    await self.start_session(text)
            else:
                if old_state:
                    logging.info("End Session")
                if self.current_session is not None:
                    await self.session_storage.update_session_energy(self.current_session, self.consumed_solar_energy, self.consumed_energy)

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        return {}

class DeviceWithState(ABC):
    """Device with a state."""

    @property
    @abstractmethod
    def state(self) -> str:
        """The state of the device."""
        pass
