"""The Device classes."""

class Integrator:
    """Integrate a measurement like power to get the energy."""

    def __init__(self):
        """Initialize the integrator."""
        self.last_measurement = None
        self.last_timestamp = None
        self._value = 0


    @property
    def value(self):
        return self._value

    def add_measurement(self, measurement: float, timestamp: float):
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


    def restore_state(self, state: float):
        self._value = state


class EnergyIntegrator:
    def __init__(self):
        self._last_consumed_energy = None
        self._consumed_solar_energy = None
        self._last_timestamp = None


    @property
    def consumed_solar_energy(self):
        return self._consumed_solar_energy

    def add_measurement(self, consumed_energy: float, self_sufficiency: float):
        if self._last_consumed_energy is not None:
            if self._consumed_solar_energy is None:
                self._consumed_solar_energy = self._last_consumed_energy
            self._consumed_solar_energy = self._consumed_solar_energy + (consumed_energy - self._last_consumed_energy) * self_sufficiency
        else:
            self._consumed_solar_energy = consumed_energy
        self._last_consumed_energy = consumed_energy


    def restore_state(self, state: float):
        self._consumed_solar_energy = state

class EnergySnapshot:
    def __init__(self, consumed_solar_energy: float, consumed_energy: float):
        self._consumed_solar_energy = consumed_solar_energy
        self._consumed_energy = consumed_energy

    @property
    def consumed_solar_energy(self) -> float:
        return self._consumed_solar_energy

    @property
    def consumed_energy(self) -> float:
        return self._consumed_energy

class Device:
    def __init__(self, name):
        self._name = name
        self._consumed_solar_energy = EnergyIntegrator()
        self._consumed_energy = None
        self._energy_snapshot = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def consumed_solar_energy(self):
        """Solar energy in kWh."""
        return self._consumed_solar_energy.consumed_solar_energy

    @property
    def consumed_energy(self):
        """Consumed energy in kWh."""
        return self._consumed_energy.state if self._consumed_energy is not None else 0.0

    def restore_state(self, consumed_solar_energy, consumed_energy):
        self._consumed_solar_energy.restore_state(consumed_solar_energy * (3600 * 1000))
        self.set_snapshot(consumed_solar_energy, consumed_energy)

    def set_snapshot(self, consumed_solar_energy, consumed_energy):
        self._energy_snapshot = EnergySnapshot(consumed_solar_energy, consumed_energy)

    @property
    def energy_snapshot(self):
        """The last energy snapshot of the device"""
        return self._energy_snapshot
    
    def store_energy_snapshot(self):
        """Stores the current values in the snapshot."""
        self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

    @property
    def extra_attributes(self):
        return {}




