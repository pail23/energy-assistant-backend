"""The Device classes."""
from datetime import datetime

class Integrator:
    def __init__(self):
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



class Device:
    def __init__(self, name):
        self._name = name    
        self._solar_energy = Integrator()
        self._consumed_energy = Integrator()      

    @property
    def name(self) -> str:
        return self._name      
    
    @property 
    def solar_energy(self):
        """Solar energy in kWh"""
        return self._solar_energy.value / (3600 * 1000)
    
    @property
    def consumed_energy(self):
        """Consumed energy in kWh"""
        return self._consumed_energy.value / (3600 * 1000)
    
    def restore_state(self, solar_energy, consumed_energy):
        self._solar_energy.restore_state(solar_energy * (3600 * 1000))
        self._consumed_energy.restore_state(consumed_energy * (3600 * 1000))

    @property
    def extra_attributes(self):
        return {}




