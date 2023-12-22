"""Device base class for all devices."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import uuid

from energy_assistant import Optimizer
from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices.analysis import DataBuffer
from energy_assistant.devices.utility_meter import UtilityMeter

from . import (
    DeferrableLoadInfo,
    EnergyIntegrator,
    EnergySnapshot,
    PowerModes,
    Session,
    SessionStorage,
    StatesRepository,
)
from .config import get_config_param

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class Device(ABC):
    """A device which tracks energy consumption."""

    def __init__(self, config: dict) -> None:
        """Create a device."""
        self._name = get_config_param(config, "name")
        self._id = uuid.UUID(get_config_param(config, "id"))
        self._consumed_solar_energy = EnergyIntegrator()
        self._energy_snapshot: EnergySnapshot | None = None
        self._supported_power_modes: list[PowerModes] = [PowerModes.DEVICE_CONTROLLED]
        self._power_mode: PowerModes = PowerModes.DEVICE_CONTROLLED
        self._utility_meters: list[UtilityMeter] = []
        self._config: dict = config.copy()

    @property
    def name(self) -> str:
        """The name of the device."""
        return self._name

    @property
    @abstractmethod
    def type(self) -> str:
        """The device type."""
        pass

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
        return not (
            len(self._supported_power_modes) == 1
            and self._supported_power_modes[0] == PowerModes.DEVICE_CONTROLLED
        )

    @property
    def config(self) -> dict:
        """Return the config dictionary."""
        return self._config

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
        return (
            self._consumed_solar_energy.consumed_solar_energy
            if self._consumed_solar_energy.consumed_solar_energy is not None
            else 0.0
        )

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
    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: DataBuffer,
    ) -> None:
        """Update the device based on the current pv availablity."""
        pass

    @abstractmethod
    async def update_state(
        self, state_repository: StatesRepository, self_sufficiency: float
    ) -> None:
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
    def energy_snapshot(self) -> EnergySnapshot | None:
        """The last energy snapshot of the device."""
        return self._energy_snapshot

    def store_energy_snapshot(self) -> None:
        """Store the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        return {}

    def get_deferrable_load_info(self) -> DeferrableLoadInfo | None:
        """Get the current deferrable load info."""
        return None

    def add_utility_meter(self, id: str) -> UtilityMeter:
        """Add a new utility meter to the device."""
        utility_meter = UtilityMeter(id)
        self._utility_meters.append(utility_meter)
        return utility_meter


class DeviceWithState(Device):
    """Device with a state."""

    def __init__(self, config: dict, session_storage: SessionStorage):
        """Create a DeviceWithState instance."""
        super().__init__(config)
        self.session_storage: SessionStorage = session_storage
        self.current_session: Session | None = None
        self._store_sessions = config.get("store_sessions", False)

    @property
    @abstractmethod
    def state(self) -> str:
        """The state of the device."""
        pass

    @property
    def has_state(self) -> bool:
        """Has this device a state."""
        return True

    async def start_session(self, text: str) -> None:
        """Start a session."""
        self.current_session = await self.session_storage.start_session(
            self.id, text, self.consumed_solar_energy, self.consumed_energy
        )

    async def update_session(self, old_state: bool, new_state: bool, text: str) -> None:
        """Update the session log."""
        if self._store_sessions:
            if new_state:
                if old_state:
                    if self.current_session is not None:
                        await self.session_storage.update_session(
                            self.current_session.id,
                            self.consumed_solar_energy,
                            self.consumed_energy,
                        )
                else:
                    LOGGER.info("Start Session")
                    await self.start_session(text)
            else:
                if old_state:
                    LOGGER.info("End Session")
                if self.current_session is not None:
                    await self.session_storage.update_session_energy(
                        self.current_session.id,
                        self.consumed_solar_energy,
                        self.consumed_energy,
                    )

    @property
    def attributes(self) -> dict[str, str]:
        """Get the attributes of the device for the UI."""
        result: dict[str, str] = {}
        if self.has_state:
            result["state"] = self.state
        if self.state == "on" and self.current_session is not None:
            result["session_time"] = str(
                (datetime.now(timezone.utc) - self.current_session.start).total_seconds()
            )
            result["session_energy"] = str(
                self.consumed_energy - self.current_session.start_consumed_energy
            )
            result["session_solar_energy"] = str(
                self.consumed_solar_energy - self.current_session.start_solar_consumed_energy
            )
        return result
