"""Mqtt connection for energy assistant."""

import logging
import random

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from energy_assistant.devices import State, StatesSingleRepository

MQTT_CHANNEL = "mqtt"


def on_message(client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:  # type: ignore
    """Handle received mqtt messages."""
    userdata.on_message_received(message.topic, str(message.payload.decode("utf-8")))


def on_connect(client: mqtt.Client, userdata, flags, rc, properties) -> None:  # type: ignore
    """Handle connecting to the mqtt server."""
    logging.info("Connected to mqtt with result code " + str(rc))
    userdata.subscribe_topics()


def on_disconnect(client: mqtt.Client, userdata, flags, rc, properties) -> None:  # type: ignore
    """Handle disconnect from the mqtt server."""
    logging.info("Disconnected to mqtt with result code " + str(rc))
    # TODO: Handle reconnect


class MqttConnection(StatesSingleRepository):
    """Connecting to mqtt."""

    def __init__(self, host: str, username: str, password: str, topic: str) -> None:
        """Create an Mqtt Connection instance."""
        super().__init__(MQTT_CHANNEL)
        self._host = host
        self._username = username
        self._password = password
        self._topic = topic
        self._subscription_topics: set = set()
        self._client: mqtt.Client | None = None

    def connect(self) -> None:
        """Connect to the mqtt server."""
        try:
            self._client = mqtt.Client(
                CallbackAPIVersion.VERSION2,
                "energy_assistant" + str(random.randrange(1024)),
                userdata=self,
            )
            self._client.username_pw_set(self._username, self._password)
            self._client.will_set(f"{self._topic}/status", payload="offline", qos=0, retain=True)
            self._client.on_message = on_message
            self._client.on_connect = on_connect
            self._client.on_disconnect = on_disconnect
            self._client.connect(self._host)
            self._client.loop_start()
        except Exception:
            logging.exception("Error while connecting mqtt ")

    def add_subscription_topic(self, topic: str) -> None:
        """Add a subscription topic."""
        if topic not in self._subscription_topics:
            self._subscription_topics.add(topic)
            if self._client is not None:
                self._client.subscribe(topic)

    def subscribe_topics(self) -> None:
        """Subscribe to the registered topics on mqtt."""
        if self._client is not None:
            for topic in self._subscription_topics:
                self._client.subscribe(topic)

    def on_message_received(self, id: str, value: str) -> None:
        """Handle a received mqtt message."""
        self._read_states[id] = State(id, value)

    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""

    def read_states(self) -> None:
        """Read the states from the channel."""

    async def async_write_states(self) -> None:
        """Send the changed states to hass."""
        self.write_states()

    def write_states(self) -> None:
        """Write the states to the channel."""
        if self._client:
            for id, state in self._write_states.items():
                self._client.publish(id, state.value)
