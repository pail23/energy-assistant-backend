"""The Device classes."""

class Integrator:
    """Integrate a measurement like power to get the energy."""

    def __init__(self) -> None:
        """Initialize the integrator."""
        self.last_measurement = None
        self.last_timestamp = None
        self._value = 0


    @property
    def value(self) -> float:
        """The current value of the integrator."""
        return self._value

    def add_measurement(self, measurement: float, timestamp: float):
        """Update the value of the integrator with and new measuremenent value."""
        if self.last_measurement is None:
            self.last_measurement = measurement
            self.last_timestamp = timestamp
        else:
            delta_t = timestamp - self.last_timestamp
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
        self._last_consumed_energy = None
        self._consumed_solar_energy = None
        self._last_timestamp = None


    @property
    def consumed_solar_energy(self) -> float:
        """The amount of solar energy which has been consumed."""
        return self._consumed_solar_energy

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

class Device:
    """A device which tracks energy consumption."""

    def __init__(self, name: str) -> None:
        """Create a device."""
        self._name = name
        self._consumed_solar_energy = EnergyIntegrator()
        self._consumed_energy = None
        self._energy_snapshot = None

    @property
    def name(self) -> str:
        """The name of the device."""
        return self._name

    @property
    def consumed_solar_energy(self) -> float:
        """Solar energy in kWh."""
        return self._consumed_solar_energy.consumed_solar_energy

    @property
    def consumed_energy(self) -> float:
        """Consumed energy in kWh."""
        return self._consumed_energy.state if self._consumed_energy is not None else 0.0

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float):
        """Restore a previously stored state of the device."""
        self._consumed_solar_energy.restore_state(consumed_solar_energy * (3600 * 1000))
        self.set_snapshot(consumed_solar_energy, consumed_energy)

    def set_snapshot(self, consumed_solar_energy: float, consumed_energy: float):
        """Set the snapshot values."""
        self._energy_snapshot = EnergySnapshot(consumed_solar_energy, consumed_energy)

    @property
    def energy_snapshot(self)-> float:
        """The last energy snapshot of the device."""
        return self._energy_snapshot

    def store_energy_snapshot(self) -> float:
        """Store the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)
