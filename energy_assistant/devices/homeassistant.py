"""Interface to the homeassistant instance."""

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from enum import StrEnum
from zoneinfo import ZoneInfo

import pandas as pd
import requests  # type: ignore
from aiohttp import ClientResponse, ClientSession, TCPConnector
from hass_client import HomeAssistantClient  # type: ignore
from hass_client.exceptions import BaseHassClientError  # type: ignore
from hass_client.utils import get_websocket_url  # type: ignore

from energy_assistant import Optimizer
from energy_assistant.constants import (
    DEFAULT_NOMINAL_DURATION,
    DEFAULT_NOMINAL_POWER,
    POWER_HYSTERESIS,
    ROOT_LOGGER_NAME,
)
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.registry import DeviceType, DeviceTypeRegistry
from energy_assistant.devices.state_value import StateValue

from . import (
    LoadInfo,
    Location,
    OnOffState,
    PowerModes,
    SessionStorage,
    State,
    StateId,
    StatesRepository,
    StatesSingleRepository,
    assign_if_available,
)
from .config import DeviceConfigMissingParameterError, get_config_param
from .device import DeviceWithState

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)
UNAVAILABLE = "unavailable"

HOMEASSISTANT_CHANNEL = "ha"


class HomeassistantState(State):
    """Abstract base class for states."""

    def __init__(self, id: str, value: str, attributes: dict | None = None) -> None:
        """Create a State instance."""
        super().__init__(id, value, attributes)

        if value == UNAVAILABLE:
            self._available = False
        else:
            self._available = True

    @property
    def name(self) -> str:
        """The name of the State."""
        if self._attributes is not None:
            return str(self._attributes.get("friendly_name"))
        return self._id

    @property
    def unit(self) -> str:
        """Unit of the state."""
        if self._attributes is not None:
            return str(self._attributes.get("unit_of_measurement"))
        return ""


@dataclass
class HistoryState:
    """Represents a history of a state."""

    time_stamp: datetime
    state: float


def convert_statistics(value: dict) -> dict:
    """Convert the times in a Home Assistant dict to date time values."""
    result = value.copy()
    result["start"] = datetime.fromtimestamp(value["start"] / 1000, UTC)
    result["end"] = datetime.fromtimestamp(value["end"] / 1000, UTC)
    return result


def convert_float(value: str) -> float:
    """Convert a value from Home Assistant to a float."""
    if value == "unavailable":
        return math.nan
    return float(value)


def convert_history(value: dict) -> HistoryState:
    """Convert a history state to a HistoryState instance."""
    return HistoryState(time_stamp=datetime.fromtimestamp(value["lu"], UTC), state=convert_float(value["s"]))


class StatisticsType(StrEnum):
    """The type of statistics which can be requested from Home Assistant."""

    MAX = "max"
    MEAN = "mean"
    MIN = "min"
    CHANGE = "change"


class StatisticsPeriod(StrEnum):
    """The statistics period which can be requested from Home Assistant."""

    FIVE_Min = "5minute"
    DAY = "day"
    HOUR = "hour"
    WEEK = "week"
    MONTH = "month"


class SourceType(StrEnum):
    """The type of the energy source."""

    GRID = "grid"
    SOLAR = "solar"


@dataclass
class EnergySource:
    """An energy source with the corresponding energy sensors."""

    source_type: SourceType
    flow_from: str
    flow_to: str | None


class HomeAssistantCommunicationError(Exception):
    """Home Assistant Communication Error."""

    def __init__(self, response: ClientResponse) -> None:
        """Create a HomeAssistantCommunicationError instance."""
        super().__init__(f"Error during communication with Home Assistant. Url={response.url} Status={response.status}")


class Homeassistant(StatesSingleRepository):
    """Home assistant proxy."""

    session: ClientSession
    hass: HomeAssistantClient
    _listen_task: asyncio.Task | None = None

    _time_zone: tzinfo | None

    def __init__(self, url: str, token: str, demo_mode: bool) -> None:
        """Create an instance of the Homeassistant class."""
        super().__init__(HOMEASSISTANT_CHANNEL)
        self._url = url
        self._token = token
        self._demo_mode = demo_mode is not None and demo_mode
        self._time_zone: tzinfo | None = None

    async def connect(self) -> None:
        """Connect to the homeassistant instance."""
        loop = asyncio.get_running_loop()
        self.session = ClientSession(
            loop=loop,
            connector=TCPConnector(
                ssl=False,
                enable_cleanup_closed=True,
                limit=4096,
                limit_per_host=100,
            ),
        )
        url = get_websocket_url(self._url)

        self.hass = HomeAssistantClient(url, self._token, self.session)
        await self.hass.connect()
        self._listen_task = asyncio.create_task(self._hass_listener())
        LOGGER.info("Connected to Homeassistant version %s", self.hass.version)

    async def disconnect(self) -> None:
        """Disconnects from home assistant."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        await self.hass.disconnect()
        await self.session.close()

    async def _hass_listener(self) -> None:
        """Start listening on the HA websockets."""
        if self._listen_task is not None:
            while not self._listen_task.cancelled():
                try:
                    # start listening will block until the connection is lost/closed
                    await self.hass.start_listening()
                except BaseHassClientError as err:
                    LOGGER.warning("Connection to HA lost due to error: %s", err)
                LOGGER.info("Connection to HA lost. Reconnecting.")
                # schedule a reload of the provider
                # self.mass.call_later(5, self.mass.config.reload_provider(self.instance_id))

    @property
    def url(self) -> str:
        """URL of the home assistant instance."""
        return self._url

    @property
    def token(self) -> str:
        """Token of the home assistant instance."""
        return self._token

    async def get_statistics(
        self,
        entity_id: str,
        start_time: datetime | None = None,
        types: list[StatisticsType] | None = None,
        period: StatisticsPeriod = StatisticsPeriod.HOUR,
    ) -> list[dict]:
        """Read the statistics for an entity."""
        if start_time is None:
            start_time = datetime.now(tz=await self.get_timezone()).replace(hour=0, minute=0, second=0, microsecond=0)
        statistics = await self.hass.send_command(
            "recorder/statistics_during_period",
            period=period,
            start_time=start_time.isoformat(),
            statistic_ids=[entity_id],
            types=types if types is not None else [],
        )
        if entity_id in statistics:
            return [convert_statistics(value) for value in statistics[entity_id]]
        return []

    async def get_history(
        self,
        entity_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[HistoryState]:
        """Get the history of a state from Home Assistant."""
        if start_time is None:
            start_time = datetime.now(tz=await self.get_timezone()).replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time is None:
            end_time = datetime.now(tz=await self.get_timezone())
        history = await self.hass.send_command(
            "history/history_during_period",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            entity_ids=[entity_id],
            no_attributes=True,
            minimal_response=True,
        )
        if entity_id in history:
            return [convert_history(value) for value in history[entity_id]]
        return []

    async def get_energy_info(self) -> dict:
        """Get the energy info from Home Assistant."""
        return await self.hass.send_command("energy/info")

    async def get_energy_prefs(self) -> list[EnergySource]:
        """Get the energy configuration from Home Assistant."""
        prefs = await self.hass.send_command("energy/get_prefs")
        sources = prefs.get("energy_sources")
        result: list[EnergySource] = []
        if sources is not None:
            for source in sources:
                flow_from = source.get("flow_from")
                flow_to = source.get("flow_to")
                if flow_from is not None and flow_to is not None:
                    energy_source = EnergySource(
                        source_type=source.get("type"),
                        flow_from=flow_from[0].get("stat_energy_from"),
                        flow_to=flow_to[0].get("stat_energy_to") if flow_to is not None else None,
                    )
                    result.append(energy_source)
                else:
                    energy_from = source.get("stat_energy_from")
                    if energy_from is not None:
                        energy_source = EnergySource(
                            source_type=source.get("type"),
                            flow_from=energy_from,
                            flow_to=None,
                        )
                        result.append(energy_source)

        return result

    async def get_solar_forecast(self) -> pd.DataFrame:
        """Get the solar forecast from Home Assistant."""
        forecast = await self.hass.send_command("energy/solar_forecast")
        df = pd.DataFrame()

        for fcst, series in forecast.items():
            df[fcst] = pd.Series(series.get("wh_hours"))
        df.index = pd.to_datetime(df.index)
        df["sum"] = df.sum(axis=1)
        freq = pd.Timedelta("60min")
        return df.resample(freq).sum().interpolate()

    async def async_read_states(self) -> None:
        """Read the states from the homeassistant instance asynchronously."""

        try:
            states = await self.hass.get_states()
            self._read_states.clear()
            for state in states:
                entity_id = state.get("entity_id")
                self._read_states[entity_id] = HomeassistantState(
                    entity_id,
                    state.get("state"),
                    state.get("attributes"),
                )
            self._template_states = None
        except Exception:
            LOGGER.exception("Exception during homeassistant update_states: ")

    async def async_write_states(self) -> None:
        """Send the changed states to hass."""
        if not self._demo_mode:
            try:
                for id, state in self._write_states.items():
                    if id.startswith("number"):
                        data = {"value": state.value}
                        await self.hass.call_service(
                            "number",
                            service="set_value",
                            service_data=data,
                            target={"entity_id": id},
                        )

                    elif id.startswith("switch"):
                        await self.hass.call_service("switch", service=f"turn_{state.value}", target={"entity_id": id})

                    elif id.startswith("sensor"):
                        headers = {
                            "Authorization": f"Bearer {self._token}",
                            "content-type": "application/json",
                        }
                        sensor_data: dict = {
                            "state": state.value,
                            "attributes": state.attributes,
                        }
                        async with self.session.post(
                            f"{self._url}/api/states/{id}",
                            headers=headers,
                            json=sensor_data,
                        ) as response:
                            if not response.ok:
                                LOGGER.error(f"State update for {id} in hass failed")
                    else:
                        LOGGER.error(f"Writing to id {id} is not yet implemented.")
            except Exception:
                LOGGER.exception("Exception during homeassistant update_states.")
            self._write_states.clear()

    def read_states(self) -> None:
        """Read the states from the homeassistant instance."""
        if self._demo_mode:
            self._read_states["sensor.solaredge_i1_ac_power"] = HomeassistantState(
                "sensor.solaredge_i1_ac_power",
                "10000",
            )
            self._read_states["sensor.solaredge_m1_ac_power"] = HomeassistantState(
                "sensor.solaredge_m1_ac_power",
                "6000",
            )
            self._read_states["sensor.keba_charge_power"] = HomeassistantState("sensor.keba_charge_power", "2500")
            self._read_states["sensor.tumbler_power"] = HomeassistantState("sensor.tumbler_power", "600")
            self._read_states["sensor.officedesk_power"] = HomeassistantState("sensor.officedesk_power", "40")
            self._read_states["sensor.rack_power"] = HomeassistantState("sensor.rack_power", "80")
        else:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "content-type": "application/json",
            }
            try:
                response = requests.get(f"{self._url}/api/states", headers=headers)

                if response.ok:
                    states = response.json()
                    self._read_states.clear()
                    for state in states:
                        entity_id = state.get("entity_id")
                        self._read_states[entity_id] = HomeassistantState(
                            entity_id,
                            state.get("state"),
                            state.get("attributes"),
                        )
                    self._template_states = None

            except Exception:
                LOGGER.exception("Exception during homeassistant update_states: ")

    def write_states(self) -> None:
        """Send the changed states to hass."""
        if not self._demo_mode:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "content-type": "application/json",
            }
            try:
                for id, state in self._write_states.items():
                    if id.startswith("number"):
                        data = {"entity_id": id, "value": state.value}
                        response = requests.post(
                            f"{self._url}/api/services/number/set_value",
                            headers=headers,
                            json=data,
                        )
                        if not response.ok:
                            LOGGER.error("State update in hass failed")
                    elif id.startswith("switch"):
                        data = {"entity_id": id}
                        response = requests.post(
                            f"{self._url}/api/services/switch/turn_{state.value}",
                            headers=headers,
                            json=data,
                        )
                        if not response.ok:
                            LOGGER.error("Turn switch update in hass failed")
                    elif id.startswith("sensor"):
                        sensor_data: dict = {
                            "state": state.value,
                            "attributes": state.attributes,
                        }
                        response = requests.post(
                            f"{self._url}/api/states/{id}",
                            headers=headers,
                            json=sensor_data,
                        )
                        if not response.ok:
                            LOGGER.error(f"State update for {id} in hass failed")
                    else:
                        LOGGER.error(f"Writing to id {id} is not yet implemented.")
            except Exception:
                LOGGER.exception("Exception during homeassistant update_states.")
            self._write_states.clear()

    async def get_config(self) -> dict:
        """Read the Homeassistant configuration."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        async with self.session.get(f"{self._url}/api/config", headers=headers) as response:
            if response.ok:
                return await response.json()
        raise HomeAssistantCommunicationError(response)

    async def get_location(self) -> Location:
        """Read the location from the Homeassistant configuration."""
        config = await self.get_config()

        return Location(
            latitude=config.get("latitude", ""),
            longitude=config.get("longitude", ""),
            elevation=config.get("elevation", ""),
            time_zone=config.get("time_zone", ""),
        )

    async def get_timezone(self) -> tzinfo:
        """Get the local timezone."""
        if self._time_zone is None:
            self._time_zone = ZoneInfo((await self.get_location()).time_zone)
        return self._time_zone


class HomeassistantDevice(DeviceWithState):
    """A generic Homeassistant device."""

    def __init__(
        self,
        device_id: uuid.UUID,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Create a generic Homeassistant device."""
        super().__init__(device_id, session_storage)
        self._device_type_registry = device_type_registry
        self._nominal_power: float | None = None
        self._nominal_duration: float | None = None
        self._is_constant: bool | None = None

        self._power_entity_id: str = ""
        self._power: State | None = None
        self._consumed_energy: State | None = None
        self._output_state: State | None = None
        self._output_id: str | None = None
        self._icon: str = "mdi-home"
        self._power_data = FloatDataBuffer()

        self._state: str = OnOffState.UNKNOWN
        self._consumed_energy_value: StateValue | None = None
        self._device_type: DeviceType | None = None

    def configure(self, config: dict) -> None:
        """Load the device configuration from the provided data."""
        super().configure(config)
        self._power_entity_id = get_config_param(config, "power")
        energy_config = config.get("energy")
        if energy_config is not None:
            self._consumed_energy_value = StateValue(energy_config)
        else:
            msg = "energy"
            raise DeviceConfigMissingParameterError(msg)

        energy_scale: float | None = config.get("energy_scale")
        if energy_scale is not None:
            self._consumed_energy_value.set_scale(energy_scale)
            LOGGER.warning(
                f"Homeassistant device with id {self.id} is configured with energy_scale. This is deprecated and will no longer be supported.",
            )

        self._output_id = config.get("output")
        self._icon = str(config.get("icon", "mdi-home"))

        if self._output_id is not None:
            self._supported_power_modes.add(PowerModes.PV)
            self._supported_power_modes.add(PowerModes.OPTIMIZED)

        manufacturer = config.get("manufacturer")
        model = config.get("model")

        if model is not None and manufacturer is not None:
            self._device_type = self._device_type_registry.get_device_type(manufacturer, model)
            self._nominal_power = config.get(
                "nominal_power",
                self._device_type.nominal_power if self._device_type else None,
            )
            self._nominal_duration = config.get(
                "nominal_duration",
                self._device_type.nominal_duration if self._device_type else None,
            )
            self._is_constant = config.get("constant", self._device_type.constant if self._device_type else None)
        else:
            self._nominal_power = config.get("nominal_power")
            self._nominal_duration = config.get("nominal_duration")
            self._is_constant = config.get("constant")
        state_detection: dict = config.get("state", {})
        if self._device_type is None and state_detection:
            state_on = state_detection.get("state_on", {})
            state_off = state_detection.get("state_off", {})
            self._device_type = DeviceType(
                str(config.get("icon", "mdi:lightning-bolt")),
                self._nominal_power if self._nominal_power is not None else DEFAULT_NOMINAL_POWER,
                (self._nominal_duration if self._nominal_duration is not None else DEFAULT_NOMINAL_DURATION),
                self._is_constant if self._is_constant is not None else False,
                state_on.get("threshold", 2),
                state_off.get("threshold", 0),
                state_off.get("upper", 0),
                state_off.get("lower", 0),
                state_off.get("for", 0),
                state_off.get("trailing_zeros_for", 10),
            )

    @property
    def type(self) -> str:
        """The device type."""
        return "homeassistant"

    async def update_state(self, state_repository: StatesRepository, self_sufficiency: float) -> None:
        """Update the own state from the states of a StatesRepository."""
        if self._output_id is not None:
            self._output_state = assign_if_available(self._output_state, state_repository.get_state(self._output_id))
        else:
            self._output_state = None
        self._power = assign_if_available(self._power, state_repository.get_state(self._power_entity_id))
        self._consumed_energy = assign_if_available(
            self._consumed_energy,
            self._consumed_energy_value.evaluate(state_repository) if self._consumed_energy_value is not None else None,
        )
        self._consumed_solar_energy.add_measurement(self.consumed_energy, self_sufficiency)
        if self._energy_snapshot is None:
            self.set_snapshot(self.consumed_solar_energy, self.consumed_energy)

        if self.has_state:
            old_state = self.state == OnOffState.ON
            if self._device_type is not None:
                self._power_data.add_data_point(self.power)
                if self.state != OnOffState.ON and self.power > self._device_type.state_on_threshold:
                    self._state = OnOffState.ON
                elif self.state != OnOffState.OFF:
                    if self.state == OnOffState.ON and self.power <= self._device_type.state_off_threshold:
                        is_between = self._device_type.state_off_for > 0 and self._power_data.is_between(
                            self._device_type.state_off_lower,
                            self._device_type.state_off_upper,
                            self._device_type.state_off_for,
                            without_trailing_zeros=True,
                        )
                        max = self._device_type.trailing_zeros_for > 0 and self._power_data.get_max_for(
                            self._device_type.trailing_zeros_for,
                        )
                        if is_between or max <= self._device_type.state_off_threshold:
                            self._state = OnOffState.OFF
                    elif self.state == OnOffState.UNKNOWN:
                        self._state = OnOffState.OFF
            new_state = self.state == OnOffState.ON
            await super().update_session(old_state, new_state, "Power State Device")

    async def update_power_consumption(
        self,
        state_repository: StatesRepository,
        optimizer: Optimizer,
        grid_exported_power_data: FloatDataBuffer,
    ) -> None:
        """Update the device based on the current pv availability."""
        if self._output_id is not None:
            state: bool = self._output_state.value == "on" if self._output_state is not None else False
            new_state = state
            if self.power_mode == PowerModes.PV:
                avg_300 = grid_exported_power_data.get_average_for(300)
                if avg_300 > self.nominal_power * (1 + POWER_HYSTERESIS):
                    new_state = True
                elif avg_300 < self.nominal_power * (1 - POWER_HYSTERESIS):
                    new_state = False
            elif self.power_mode == PowerModes.OPTIMIZED:
                power = optimizer.get_optimized_power(self._id)
                new_state = power > 0
            if state != new_state:
                state_repository.set_state(
                    StateId(
                        id=self._output_id,
                        channel=HOMEASSISTANT_CHANNEL,
                    ),
                    "on" if new_state else "off",
                )

    @property
    def consumed_energy(self) -> float:
        """The consumed energy of the device."""
        return self._consumed_energy.numeric_value if self._consumed_energy is not None else 0.0

    @property
    def icon(self) -> str:
        """The icon of the device."""
        return self._icon

    @property
    def power(self) -> float:
        """The current power used by the device."""
        return self._power.numeric_value if self._power else 0.0

    @property
    def available(self) -> bool:
        """Is the device available?."""
        return (
            self._consumed_energy is not None
            and self._consumed_energy.available
            and self._power is not None
            and self._power.available
        )

    @property
    def nominal_power(self) -> float:
        """The nominal power of the device."""
        return self._nominal_power if self._nominal_power is not None else DEFAULT_NOMINAL_POWER

    def restore_state(self, consumed_solar_energy: float, consumed_energy: float) -> None:
        """Restore a previously stored state."""
        super().restore_state(consumed_solar_energy, consumed_energy)
        self._consumed_energy = HomeassistantState("", str(consumed_energy))

    @property
    def state(self) -> str:
        """The state of the device. The state is `on` in case the device is running."""
        return self._state

    @property
    def has_state(self) -> bool:
        """Has this device a state."""
        return self._device_type is not None

    def get_load_info(self) -> LoadInfo | None:
        """Get the current deferrable load info."""
        if self._nominal_power is not None and self._nominal_duration is not None:
            if self.power_mode == PowerModes.OPTIMIZED:
                return LoadInfo(
                    device_id=self.id,
                    nominal_power=self._nominal_power,
                    duration=self._nominal_duration,
                    is_continous=False,
                    is_constant=self._is_constant if self._is_constant is not None else False,
                    is_deferrable=True,
                )

            if self.state == OnOffState.ON:
                return LoadInfo(
                    device_id=self.id,
                    nominal_power=self._nominal_power,
                    duration=self._nominal_duration - self.session_duration,
                    is_continous=False,
                    is_constant=self._is_constant if self._is_constant is not None else False,
                    is_deferrable=False,
                )

        return None
