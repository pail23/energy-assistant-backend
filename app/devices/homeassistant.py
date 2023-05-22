import requests
from datetime import datetime
from . import Device
from .mqtt import MqttDevice


class State:
    def __init__(self, entity_id:str, state:str, attributes:dict):
        try:
            self._state = float(state)
        except ValueError:
            self._state = state
        self._attributes = attributes
        self._entity_id = entity_id

    @property
    def state(self):
        return self._state
    
    @property
    def unit(self) -> str:
        if self._attributes is not None:
            return self._attributes.get("unit_of_measurement")
        return None
    
    @property 
    def name(self) -> str:
        if self._attributes is not None:
            return self._attributes.get("friendly_name")
        return self._entity_id

    @property
    def entity_id(self) -> str:
        return self._entity_id        
        

class Homeassistant:
    def __init__(self, url, token):
        self._url = url
        self._states = {}
        self._token = token
    

    def update_states(self):
        headers = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        time_stamp = datetime.now().timestamp()
        response = requests.get(
            f"{self._url}/api/states", headers=headers)
        delta_t = datetime.now().timestamp() - time_stamp
        if response.ok:
            states = response.json()
            self._states = {}
            for state in states:
                entity_id = state.get("entity_id")
                self._states[entity_id] = State(entity_id, state.get("state"), state.get("attributes"))

    def get_state(self, entity_id) -> State:
        return self._states.get(entity_id)
    

class HomeassistantDevice(Device):
    def __init__(self, name, entity_id):
        super().__init__(name)
        self._entity_id = entity_id
        self._state = None


    def update_state(self, hass:Homeassistant, self_sufficiency: float):
        self._state = hass.get_state(self._entity_id)

    @property
    def icon(self):
        return "mdi:mdi-car-electric"
    
    @property
    def state(self):
        return self._state.state if self._state is not None else 0.0


STIEBEL_ELTRON_POWER = 5000
class StiebelEltronDevice(HomeassistantDevice):
    def __init__(self, name, state_entity_id, actual_temp_entity_id):
        super().__init__(name, state_entity_id)    
        self._actual_temp_entity_id = actual_temp_entity_id
        self._actual_temp = None
        self._state = None

    def update_state(self, hass:Homeassistant, self_sufficiency: float):
        self._state = hass.get_state(self._entity_id)
        time_stamp = datetime.now().timestamp()
        self._solar_energy.add_measurement(self.state * self_sufficiency, time_stamp)
        self._consumed_energy.add_measurement(self.state, time_stamp)     
        self._actual_temp = hass.get_state(self._actual_temp_entity_id)

    @property
    def state(self):
        if self._state is not None:
            return STIEBEL_ELTRON_POWER if self._state.state == 'on' else 0.0
        else:
            return 0.0

    @property
    def actual_temperature(self):
        return self._actual_temp.state if self._actual_temp is not None else 0.0
    
    @property
    def icon(self):
        return "mdi:mdi-heat-pump"
    
    @property
    def extra_attributes(self):
        return {"actual_temperature": self.actual_temperature}    
    

class Home(Device):
    def __init__(self, name, solar_entity_id, grid_supply_entity_id):
        super().__init__(name)
        self._solar_entity_id = solar_entity_id
        self._grid_supply_entity_id = grid_supply_entity_id
        self._solar_production = None
        self._grid_supply = None
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


    def update_state_from_hass(self, hass:Homeassistant):
        time_stamp = datetime.now().timestamp()
        self._solar_production = hass.get_state(self._solar_entity_id) 
        self._grid_supply = hass.get_state(self._grid_supply_entity_id)    
        self._solar_energy.add_measurement(self.solar_self_consumption, time_stamp)
        self._consumed_energy.add_measurement(self.home_consumption, time_stamp)            
        for device in self.devices:
            if isinstance(device, HomeassistantDevice):
                device.update_state(hass, self.self_sufficiency)


    def update_state_from_mqtt(self, topic: str, message: str):
        for device in self.devices:
            if isinstance(device, MqttDevice):
                device.update_state(topic, message, self.self_sufficiency)


    def mqtt_topics(self):
        result = [self._solar_entity_id, self._grid_supply_entity_id]
        for device in self.devices:
            if isinstance(device, MqttDevice):
                result.append(device.mqtt_topic)        
        return result

    @property
    def icon(self):
        return "mdi:mdi-home"
    
    @property
    def solar_production(self)-> float:
        return self._solar_production.state if self._solar_production is not None else 0.0
    
    @property
    def grid_supply(self)-> float:
        return self._grid_supply.state if self._grid_supply is not None else 0.0