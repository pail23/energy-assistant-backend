"""Tests for the heat pumpts."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from energy_assistant import Optimizer
from energy_assistant.devices import PowerModes, Session, SessionStorage, State, StateId, StatesRepository
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.heat_pump import HeatPumpDevice, SGReadyHeatPumpDevice
from energy_assistant.settings import settings
from energy_assistant.storage.config import ConfigStorage


class SessionStorageMock(SessionStorage):
    """Session storage base class."""

    async def start_session(
        self,
        device_id: uuid.UUID,
        text: str,
        solar_consumed_energy: float,
        consumed_energy: float,
    ) -> Session:
        """Start a new session."""

    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""

    async def update_session_energy(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""


@pytest.fixture()
def session_storage() -> SessionStorage:
    """Session storage mock."""
    return SessionStorageMock()


class MockStateReposity(StatesRepository):
    """Mock for the StateRepository."""

    def __init__(self) -> None:
        """Create a MockStateRepository instance."""
        self._write_states: dict = {}

    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""
        _id = id if isinstance(id, str) else id.id
        return State(_id, "off") if _id.startswith("switch") else State(_id, "123")

    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""
        raise NotImplementedError

    def get_template_states(self) -> dict:
        """Get a states from the repository."""
        return {}

    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""
        _id = id if isinstance(id, str) else id.id
        self._write_states[_id] = value

    @property
    def channel(self) -> str:
        """Get the channel of the State Repository."""
        return "test"

    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""
        raise NotImplementedError

    async def async_write_states(self) -> None:
        """Send the changed states to hass."""
        raise NotImplementedError

    def read_states(self) -> None:
        """Read the states from the channel."""
        raise NotImplementedError

    def write_states(self) -> None:
        """Write the states to the channel."""
        raise NotImplementedError


@pytest.fixture()
def state_repository() -> StatesRepository:
    """State repository mock."""
    return MockStateReposity()


class OptimizerMock(Optimizer):
    """Mock class for optimizers."""

    def get_optimized_power(self, device_id: uuid.UUID) -> float:
        """Get the optimized power budget for a give device."""
        return 3500


@pytest.fixture()
def optimizer() -> Optimizer:
    """Optimizery mock."""
    return OptimizerMock()


DEVICE_ID: str = "39a6c904-3266-450a-aeba-851915ba8249"

HEATPUMP_CONFIG = {
    "name": "my heatpump",
    "id": DEVICE_ID,
    "state": "binary_sensor.heating_state",
    "energy": "sensor.heating_energy",
    "temperature": "sensor.heating_temperature",
    "nominal_power": 1500,
}

CONTROLLABLE_HEATPUMP_CONFIG = {
    "name": "my heatpump",
    "id": DEVICE_ID,
    "state": "binary_sensor.heating_state",
    "energy": "sensor.heating_energy",
    "temperature": "sensor.heating_temperature",
    "nominal_power": 1500,
    "comfort_target_temperature": "number.water_temperature_target",
    "target_temperature_normal": 52,
    "target_temperatrure_pv": 55,
}

SG_READY_CONFIG = {
    "name": "my heatpump",
    "id": DEVICE_ID,
    "heating": {
        "state": "binary_sensor.heating_state",
        "energy": "sensor.heating_energy",
        "temperature": "sensor.heating_temperature",
    },
    "water": {
        "state": "binary_sensor.water_heating_state",
        "energy": "sensor.water_heating_energy",
        "temperature": "sensor.water_heating_temperature",
    },
    "nominal_power": 1500,
    "output": "switch.sg_ready",
}


@pytest.mark.asyncio()
async def test_init_heatpump(session_storage: SessionStorage, state_repository: StatesRepository) -> None:
    """Test initializing a heat pump."""

    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    device_id = uuid.UUID(DEVICE_ID)

    heat_pump = HeatPumpDevice(device_id, session_storage)
    heat_pump.configure(HEATPUMP_CONFIG)
    assert heat_pump.icon == "mdi-heat-pump"

    await heat_pump.update_state(state_repository, 0.5)

    assert heat_pump.consumed_energy == 123
    assert heat_pump.consumed_solar_energy == 61.5
    assert heat_pump.attributes == {"state": "123", "actual_temperature": "123.0 °C"}
    assert len(heat_pump.supported_power_modes) == 1


@pytest.mark.asyncio()
async def test_init_controllable_heatpump(session_storage: SessionStorage, state_repository: StatesRepository) -> None:
    """Test initializing a heat pump."""
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    device_id = uuid.UUID(DEVICE_ID)

    heat_pump = HeatPumpDevice(device_id, session_storage)
    heat_pump.configure(CONTROLLABLE_HEATPUMP_CONFIG)
    assert heat_pump.icon == "mdi-heat-pump"

    await heat_pump.update_state(state_repository, 0.5)

    assert heat_pump.consumed_energy == 123
    assert heat_pump.consumed_solar_energy == 61.5
    assert heat_pump.attributes == {"state": "123", "actual_temperature": "123.0 °C"}
    assert len(heat_pump.supported_power_modes) == 3


@pytest.mark.asyncio()
async def test_init_sgready_heatpump(
    session_storage: SessionStorage,
    state_repository: StatesRepository,
    optimizer: Optimizer,
) -> None:
    """Test initializing a sg ready heat pump."""
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    device_id = uuid.UUID(DEVICE_ID)

    heat_pump = SGReadyHeatPumpDevice(device_id, session_storage)
    heat_pump.configure(SG_READY_CONFIG)
    assert heat_pump.icon == "mdi-heat-pump"

    await heat_pump.update_state(state_repository, 0.5)

    assert heat_pump.consumed_energy == 246
    assert heat_pump.consumed_solar_energy == 123
    assert heat_pump.attributes == {
        "state": "off",
        "heating_actual_temperature": "123.0 °C",
        "water_heating_actual_temperature": "123.0 °C",
        "heatpump_state": "off",
    }

    data_buffer = FloatDataBuffer()
    for x in range(20):
        d = datetime.now(UTC) - timedelta(minutes=x)
        data_buffer.add_data_point(x * 1000, d)
    await heat_pump.update_power_consumption(state_repository, optimizer, data_buffer)
    assert data_buffer.average() == 9500
    heat_pump.set_power_mode(PowerModes.PV)
    await heat_pump.update_power_consumption(state_repository, optimizer, data_buffer)
    assert state_repository._write_states["switch.sg_ready"] == "on"
    assert data_buffer.average() == 9500
