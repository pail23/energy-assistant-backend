"""The Device classes."""
from abc import ABC, abstractmethod
from typing import Optional


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
        self._last_consumed_energy : Optional[float]  = None
        self._consumed_solar_energy : Optional[float] = None
        self._last_timestamp : Optional[float] = None


    @property
    def consumed_solar_energy(self) -> float:
        """The amount of solar energy which has been consumed."""
        return self._consumed_solar_energy if self._consumed_solar_energy else 0.0

    def add_measurement(self, consumed_energy: float, self_sufficiency: float) -> None:
        """Update the value of the integrator with and new measuremenent value."""
        if self._last_consumed_energy is not None:
            if self._consumed_solar_energy is None:
                self._consumed_solar_energy = self._last_consumed_energy
            self._consumed_solar_energy = self._consumed_solar_energy + (consumed_energy - self._last_consumed_energy) * self_sufficiency
        else:
            self._consumed_solar_energy = consumed_energy
        self._last_consumed_energy = consumed_energy


    def restore_state(self, state: float) -> None:
        """Restores the integrator value with a previously saved state."""
        self._consumed_solar_energy = state

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



class Device(ABC):
    """A device which tracks energy consumption."""

    def __init__(self, name: str) -> None:
        """Create a device."""
        self._name = name
        self._consumed_solar_energy = EnergyIntegrator()
       # self._consumed_energy: Optional[float] = None
        self._energy_snapshot: Optional[EnergySnapshot] = None

    @property
    def name(self) -> str:
        """The name of the device."""
        return self._name

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
    def icon(self) -> str:
        """Icon for the device."""
        pass

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state of the device."""
        self._consumed_solar_energy.restore_state(consumed_solar_energy * (3600 * 1000))
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
