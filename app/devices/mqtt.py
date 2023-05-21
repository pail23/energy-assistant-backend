from datetime import datetime
from . import Device

class MqttDevice(Device):
    def __init__(self, name, mqtt_topic):
        super().__init__(name)
        self.mqtt_topic = mqtt_topic

class EvccDevice(MqttDevice):
    def __init__(self, name, mqtt_topic):
        super().__init__(name, mqtt_topic)
        self.state = None

    def update_state(self, topic: str, message: str, self_sufficiency: float):
        if topic == self.mqtt_topic:
            self.state = float(message)
            time_stamp = datetime.now().timestamp()
            self._solar_energy.add_measurement(self.state * self_sufficiency, time_stamp)
            self._consumed_energy.add_measurement(self.state, time_stamp)   

    @property
    def icon(self):
        return "mdi:mdi-car-electric"