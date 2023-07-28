"""The Device classes."""
from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import Optional
import uuid


class SessionStorage(ABC):
    """Session storage base class."""

    @abstractmethod
    async def start_session(self, device_id: uuid.UUID, text: str, solar_consumed_energy: float, consumed_energy: float) -> int:
        """Start a new session."""
        pass

    @abstractmethod
    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        pass

class Integrator:
    """Integrate a measurement like power to get the energy."""

    def __init__(self) -> None:
        """Initialize the integrator."""
        self.last_measurement : Optional[float] = None
        self.last_timestamp : Optional[float] = None
        self._value : float = 0.0


    @property
    def value(self) -> float:
        """The current value of the integrator."""
        return self._value

    def add_measurement(self, measurement: float, timestamp: float) -> None:
        """Update the value of the integrator with and new measuremenent value."""
        if self.last_measurement is None:
            self.last_measurement = measurement
            self.last_timestamp = timestamp
        else:
            delta_t = timestamp - self.last_timestamp if self.last_timestamp else 0.0
            self.last_timestamp = timestamp
            # print("Delta t: "+ str(delta_t))
            if delta_t > 0.1:
                if measurement > self.last_measurement:
                    self._value = self._value + (delta_t * (self.last_measurement + (measurement - self.last_measurement) / 2))
                else:
                    self._value = self._value + (delta_t * (measurement + (self.last_measurement - measurement) / 2))


    def restore_state(self, state: float) -> None:
        """Restore the integrator value with a previously saved state."""
        self._value = state


class EnergyIntegrator:
    """Integrates energy based on a real measurement and a self sufficiency value in order to sum up the consumed solar energy."""

    def __init__(self) -> None:
        """Create an energy integrator."""
        self._last_consumed_energy : float = 0.0
        self._consumed_solar_energy : float = 0.0

    @property
    def consumed_solar_energy(self) -> float:
        """The amount of solar energy which has been consumed."""
        return self._consumed_solar_energy

    def add_measurement(self, consumed_energy: float, self_sufficiency: float) -> None:
        """Update the value of the integrator with and new measuremenent value."""
        self._consumed_solar_energy = self._consumed_solar_energy + (consumed_energy - self._last_consumed_energy) * self_sufficiency
        self._last_consumed_energy = consumed_energy


    def restore_state(self, consumed_solar_energy: float, last_consumed_energy: float) -> None:
        """Restores the integrator value with a previously saved state."""
        self._consumed_solar_energy = consumed_solar_energy
        self._last_consumed_energy = last_consumed_energy

class EnergySnapshot:
    """Stores an snapshot of the current energy consumption values."""

    def __init__(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Create an energy snapshot."""
        self._consumed_solar_energy = consumed_solar_energy
        self._consumed_energy = consumed_energy

    @property
    def consumed_solar_energy(self) -> float:
        """The amount of consumed solar energy."""
        return self._consumed_solar_energy

    @property
    def consumed_energy(self) -> float:
        """The total amount of consumed energy."""
        return self._consumed_energy

class HomeEnergySnapshot(EnergySnapshot):
    """Stores an snapshot of the current energy consumption values."""

    def __init__(self, consumed_solar_energy: float, consumed_energy: float, solar_produced_energy: float, grid_imported_energy:float, grid_exported_energy:float) -> None:
        """Create an energy snapshot."""
        self._consumed_solar_energy = consumed_solar_energy
        self._consumed_energy = consumed_energy
        self._produced_solar_energy = solar_produced_energy
        self._grid_imported_energy = grid_imported_energy
        self._grid_exported_energy = grid_exported_energy

    @property
    def consumed_solar_energy(self) -> float:
        """The amount of consumed solar energy."""
        return self._consumed_solar_energy

    @property
    def consumed_energy(self) -> float:
        """The total amount of consumed energy."""
        return self._consumed_energy

    @property
    def produced_solar_energy(self) -> float:
        """The total amount of produced solar energy."""
        return self._produced_solar_energy

    @property
    def grid_imported_energy(self) -> float:
        """The total amount of energy imported from the grid."""
        return self._grid_imported_energy

    @property
    def grid_exported_energy(self) -> float:
        """The total amount of energy exported to the grid."""
        return self._grid_exported_energy

class State:
    """Base class for States."""

    def __init__(self, id:str, value:str) -> None:
        """Create a state instance."""
        self._id = id
        self._value = value
        self._available = True

    @property
    def id(self) -> str:
        """Id of the state."""
        return self._id

    @property
    def available(self) -> bool:
        """Availability of the state."""
        return self._available

    @property
    def value(self) -> str:
        """State of the state as string."""
        return self._value

    @property
    def numeric_value(self) -> float:
        """Numeric state of the state."""
        try:
            return float(self._value)
        except ValueError:
            return 0.0

def assign_if_available(old_state: State | None, new_state: State | None) -> State | None:
    """Return new state in case the state is available, otherwise old state."""
    if new_state and new_state.available:
        return new_state
    else:
        return old_state


class StatesRepository:
    """Base class for a state repositiroy."""

    def __init__(self) -> None:
        """Create a StatesRepository instance."""
        self._read_states : dict[str, State] = dict[str, State]()
        self._write_states : dict[str, State] = dict[str, State]()

    def get_state(self, id:str) -> State | None:
        """Get a state from the repositiory."""
        return self._read_states.get(id)

    def set_state(self, id:str, value: str) -> None:
        """Set a state in the repository."""
        self._write_states[id] = State(id, value)

class PowerModes(StrEnum):
    """Power modes for controlling the device."""

    DEVICE_CONTROLLED = auto()
    OFF = auto()
    PV = auto()
    MIN_PV = auto()
    FAST = auto()



class Device(ABC):
    """A device which tracks energy consumption."""

    def __init__(self, id: str, name: str, session_storage: SessionStorage) -> None:
        """Create a device."""
        self._name = name
        self._id = uuid.UUID(id)
        self._consumed_solar_energy = EnergyIntegrator()
        self._energy_snapshot: EnergySnapshot | None = None
        self.session_storage: SessionStorage = session_storage
        self.current_session : int | None = None
        self._supported_power_modes : list[PowerModes] = [PowerModes.DEVICE_CONTROLLED]
        self._power_mode : PowerModes = PowerModes.DEVICE_CONTROLLED

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
    async def update_power_consumption(self, state_repository: StatesRepository, grid_exported_power: float) -> None:
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
    def energy_snapshot(self)-> Optional[EnergySnapshot]:
        """The last energy snapshot of the device."""
        return self._energy_snapshot

    def store_energy_snapshot(self) -> None:
        """Store the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

    async def start_session(self, text: str) -> None:
        """Start a session."""
        self.current_session = await self.session_storage.start_session(self._id, text,self.consumed_solar_energy, self.consumed_energy)

    async def update_session(self) -> None:
        """Update a running session."""
        if self.current_session is not None:
            await self.session_storage.update_session(self.current_session, self.consumed_solar_energy, self.consumed_energy)



class DeviceConfigException(Exception):
    """Device configuration exception."""

    pass

def get_config_param(config: dict, param: str) -> str:
    """Get a config paramter as string or raise an exception if the parameter is not available."""
    result = config.get(param)
    if result is None:
        raise DeviceConfigException(f"Parameter {param} is missing in the configuration")
    else:
        return str(result)
