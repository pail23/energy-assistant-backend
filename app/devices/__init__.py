"""The Device classes."""
from datetime import datetime

class Integrator:
    def __init__(self):
        self.last_measurement = None
        self.last_timestamp = None
        self._value = None


    @property
    def value(self):
        return self._value
    
    def add_measurement(self, measurement: float, timestamp: float):
        if self.last_measurement is None:
            self.last_measurement = measurement
            self.last_timestamp = timestamp
            self._value = 0
        else:
            delta_t = timestamp - self.last_timestamp
            self.last_timestamp = timestamp
            print("Delta t: "+ str(delta_t))
            if delta_t > 0.1:
                if measurement > self.last_measurement:
                    self._value = self._value + (delta_t * (self.last_measurement + (measurement - self.last_measurement) / 2))
                else:
                    self._value = self._value + (delta_t * (measurement + (self.last_measurement - measurement) / 2))


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

class HomeassitantDevice(Device):
    def __init__(self, name, mqtt_topic):
        super().__init__(name)
        self.name = name
        self.mqtt_topic = mqtt_topic
        self.state = None


    def update_state(self, topic: str, message: str):
        if topic == self.mqtt_topic + "/state":
            self.state = float(message)

class EvccDevice(Device):
    def __init__(self, name, mqtt_topic):
        super().__init__(name)
        self.mqtt_topic = mqtt_topic
        self.state = None

    def update_state(self, topic: str, message: str, self_sufficiency: float):
        if topic == self.mqtt_topic:
            self.state = float(message)
            time_stamp = datetime.now().timestamp()
            self._solar_energy.add_measurement(self.state * self_sufficiency, time_stamp)
            self._consumed_energy.add_measurement(self.state, time_stamp)   

class Home(Device):
    def __init__(self, name, solar_mqtt_topic, grid_supply_mqtt_topic):
        super().__init__(name)
        self.solar_mqtt_topic = solar_mqtt_topic
        self.grid_supply_mqtt_topic = grid_supply_mqtt_topic
        self.solar_production = 0
        self.grid_supply = 0
        self.devices = []
     

    def add_device(self, device):
        self.devices.append(device)
        
    @property
    def home_consumption(self):
        result = self.solar_production - self.grid_supply
        if result > 0:
            return result
        else:
            return 0

    @property
    def solar_self_consumption(self):
        if self.grid_supply < 0:
            return self.solar_production
        else:
            return self.solar_production - self.grid_supply


    @property
    def self_sufficiency(self):
        hc = self.home_consumption
        if hc > 0:
            return self.solar_self_consumption / hc
        else:
            return 0


    def update_state(self, topic: str, message: str):
        time_stamp = datetime.now().timestamp()
        if topic == self.solar_mqtt_topic + "/state":
            self.solar_production = float(message)    
            self._solar_energy.add_measurement(self.solar_self_consumption, time_stamp)
            self._consumed_energy.add_measurement(self.home_consumption, time_stamp)            
        elif topic == self.grid_supply_mqtt_topic + "/state":
            self.grid_supply = float(message)    
            print("Consumption: ", end='')
            self._solar_energy.add_measurement(self.solar_self_consumption, time_stamp)
            self._consumed_energy.add_measurement(self.home_consumption, time_stamp)                 
        for device in self.devices:
            device.update_state(topic, message, self.self_sufficiency)


    def mqtt_topics(self):
        result = [self.solar_mqtt_topic, self.grid_supply_mqtt_topic]
        for device in self.devices:
            result.append(device.mqtt_topic)        
        return result


