"""The Device classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    import uuid
    from datetime import datetime, tzinfo


@dataclass
class LoadInfo:
    """Information about a deferrable load."""

    device_id: uuid.UUID
    nominal_power: float
    duration: float
    is_continous: bool
    is_constant: bool = False
    start_timestep: int = 0
    end_timestep: int = 0
    is_deferrable: bool = True


@dataclass
class Session:
    """Session data class."""

    id: int
    start: datetime
    start_solar_consumed_energy: float
    start_consumed_energy: float


class SessionStorage(ABC):
    """Session storage base class."""

    @abstractmethod
    async def start_session(
        self,
        device_id: uuid.UUID,
        text: str,
        solar_consumed_energy: float,
        consumed_energy: float,
    ) -> Session:
        """Start a new session."""

    @abstractmethod
    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""

    @abstractmethod
    async def update_session_energy(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""


class Integrator:
    """Integrate a measurement like power to get the energy."""

    def __init__(self) -> None:
        """Initialize the integrator."""
        self.last_measurement: float | None = None
        self.last_timestamp: float | None = None
        self._value: float = 0.0

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
                    self._value = self._value + (
                        delta_t * (self.last_measurement + (measurement - self.last_measurement) / 2)
                    )
                else:
                    self._value = self._value + (delta_t * (measurement + (self.last_measurement - measurement) / 2))

    def restore_state(self, state: float) -> None:
        """Restore the integrator value with a previously saved state."""
        self._value = state


class EnergyIntegrator:
    """Integrates energy based on a real measurement and a self sufficiency value in order to sum up the consumed solar energy."""

    def __init__(self) -> None:
        """Create an energy integrator."""
        self._last_consumed_energy: float = 0.0
        self._consumed_solar_energy: float = 0.0

    @property
    def consumed_solar_energy(self) -> float:
        """The amount of solar energy which has been consumed."""
        return self._consumed_solar_energy

    def add_measurement(self, consumed_energy: float, self_sufficiency: float) -> None:
        """Update the value of the integrator with and new measuremenent value."""
        self._consumed_solar_energy = (
            self._consumed_solar_energy + (consumed_energy - self._last_consumed_energy) * self_sufficiency
        )
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

    def __init__(
        self,
        produced_solar_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
    ) -> None:
        """Create an energy snapshot."""
        self._produced_solar_energy = produced_solar_energy
        self._grid_imported_energy = grid_imported_energy
        self._grid_exported_energy = grid_exported_energy

    @property
    def consumed_energy(self) -> float:
        """The total amount of consumed energy."""
        return self.grid_imported_energy - self.grid_exported_energy + self.produced_solar_energy

    @property
    def consumed_solar_energy(self) -> float:
        """Consumed solar energy in kWh."""
        return self.produced_solar_energy - self.grid_exported_energy

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


class OnOffState(StrEnum):
    """Representation of a on/off state."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, label: str) -> OnOffState:
        """Convert a string to a OnOffState."""
        label = label.lower()
        if label == "on":
            return cls.ON
        if label == "off":
            return cls.OFF
        return cls.UNKNOWN

    @classmethod
    def from_bool(cls, value: bool) -> OnOffState:
        """Convert a bool to a OnOffState."""
        return cls.ON if value else cls.OFF


class State:
    """Base class for States."""

    def __init__(self, id: str, value: str, attributes: dict | None = None) -> None:
        """Create a state instance."""
        self._id = id
        self._value = value
        self._attributes = attributes if attributes is not None else {}
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

    @property
    def attributes(self) -> dict:
        """Attributes of the state."""
        return self._attributes


def assign_if_available(old_state: State | None, new_state: State | None) -> State | None:
    """Return new state in case the state is available, otherwise old state."""
    if new_state and new_state.available:
        return new_state
    return old_state


@dataclass(frozen=True, eq=True)
class StateId:
    """The id of a state."""

    id: str
    channel: str


class StatesRepository(ABC):
    """Abstract base class for a state repositiroy."""

    @abstractmethod
    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""

    @abstractmethod
    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""

    @abstractmethod
    def get_template_states(self) -> dict:
        """Get a states from the repository."""

    @abstractmethod
    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""

    @property
    @abstractmethod
    def channel(self) -> str:
        """Get the channel of the State Repository."""

    @abstractmethod
    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""

    @abstractmethod
    async def async_write_states(self) -> None:
        """Send the changed states to hass."""

    @abstractmethod
    def read_states(self) -> None:
        """Read the states from the channel."""

    @abstractmethod
    def write_states(self) -> None:
        """Write the states to the channel."""


class StatesSingleRepository(StatesRepository):
    """Base class for a state repositiroy."""

    def __init__(self, channel: str) -> None:
        """Create a StatesRepository instance."""
        self._channel = channel
        self._read_states: dict[str, State] = dict[str, State]()
        self._write_states: dict[str, State] = dict[str, State]()
        self._template_states: dict[str, dict | Any] | None = None

    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""
        if isinstance(id, str):
            return self._read_states.get(id)
        return self._read_states.get(id.id)

    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""
        return {k: v.numeric_value for k, v in self._read_states.items()}

    def get_template_states(self) -> dict:
        """Get template states from the repository."""
        if self._template_states is None:
            self._template_states = {}
            states = self.get_numeric_states().items()
            for k, v in states:
                parts = k.split(".")
                if len(parts) > 1:
                    type = parts[0]
                    attribute = parts[1]
                    if type in self._template_states:
                        self._template_states[type][attribute] = v
                    else:
                        self._template_states[type] = {attribute: v}
                else:
                    self._template_states[k] = v
        return self._template_states

    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""
        self._write_states[id.id] = State(id.id, value, attributes)

    @property
    def channel(self) -> str:
        """Get the channel of the State Repository."""
        return self._channel


class StatesMultipleRepositories(StatesRepository):
    """Base class for a state repositiroy."""

    def __init__(self, repositories: list[StatesRepository]) -> None:
        """Create a StatesRepository instance."""
        self._repositories = repositories

    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""
        if isinstance(id, StateId):
            for repository in self._repositories:
                if repository.channel == id.channel:
                    result = repository.get_state(id)
                    if result is not None:
                        return result
        else:
            for repository in self._repositories:
                result = repository.get_state(id)
                if result is not None:
                    return result
        return None

    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""
        result: dict[str, float] = {}
        for reposititory in self._repositories:
            result = {**result, **reposititory.get_numeric_states()}
        return result

    def get_template_states(self) -> dict:
        """Get template states from the repository."""
        result: dict = {}
        for reposititory in self._repositories:
            result = {**result, **reposititory.get_template_states()}
        return result

    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""
        for repository in self._repositories:
            if id.channel == repository.channel:
                repository.set_state(id, value, attributes)

    @property
    def channel(self) -> str:
        """Get the channel of the State Repository."""
        return "multiple"

    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""
        for repository in self._repositories:
            await repository.async_read_states()

    def read_states(self) -> None:
        """Read the states from the channel."""
        for repository in self._repositories:
            repository.read_states()

    async def async_write_states(self) -> None:
        """Send the changed states to hass."""
        for repository in self._repositories:
            await repository.async_write_states()

    def write_states(self) -> None:
        """Write the states to the channel."""
        for repository in self._repositories:
            repository.write_states()


class PowerModes(StrEnum):
    """Power modes for controlling the device."""

    DEVICE_CONTROLLED = auto()
    OFF = auto()
    PV = auto()
    MIN_PV = auto()
    FAST = auto()
    OPTIMIZED = auto()


@dataclass
class Location:
    """Location of the home."""

    time_zone: str
    latitude: str
    longitude: str
    elevation: str

    def get_time_zone(self) -> tzinfo:
        """Get the timezone."""
        return ZoneInfo(self.time_zone)
