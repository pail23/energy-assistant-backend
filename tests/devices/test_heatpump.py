"""Tests for the heat pumpts."""

import uuid

import pytest

from energy_assistant.devices import Session, SessionStorage, State, StateId, StatesRepository
from energy_assistant.devices.heat_pump import HeatPumpDevice, SGReadyHeatPumpDevice


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
        pass


    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        pass


    async def update_session_energy(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        pass

@pytest.fixture
def session_storage() -> SessionStorage:
    """Session storage mock."""
    return SessionStorageMock()

class MockStateReposity(StatesRepository):
    """Mock for the StateRepository."""

    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""
        _id = id if isinstance(id, str) else id.id
        return State(_id, "123")

    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""
        raise NotImplementedError()

    def get_template_states(self) -> dict:
        """Get a states from the repository."""
        raise NotImplementedError()

    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""
        raise NotImplementedError()

    @property
    def channel(self) -> str:
        """Get the channel of the State Repository."""
        return "test"

    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""
        raise NotImplementedError()

    async def async_write_states(self) -> None:
        """Send the changed states to hass."""
        raise NotImplementedError()

    def read_states(self) -> None:
        """Read the states from the channel."""
        raise NotImplementedError()

    def write_states(self) -> None:
        """Write the states to the channel."""
        raise NotImplementedError()


@pytest.fixture
def state_repository() -> StatesRepository:
    """State repository mock."""
    return MockStateReposity()

HEATPUMP_CONFIG ={
    "name": "my heatpump",
    "id": uuid.UUID("39a6c904-3266-450a-aeba-851915ba8249"),
    "state": "binary_sensor.heating_state",
    "energy": "sensor.heating_energy",
    "temperature": "sensor.heating_temperature",
    "nominal_power": 3500,
}

SG_READY_CONFIG ={
    "name": "my heatpump",
    "id": uuid.UUID("3b7367fc-fb4c-4670-acde-16b4af9329f4"),
    "heating":{
        "state": "binary_sensor.heating_state",
        "energy": "sensor.heating_energy",
        "temperature": "sensor.heating_temperature",
    },
    "water":{
        "state": "binary_sensor.water_heating_state",
        "energy": "sensor.water_heating_energy",
        "temperature": "sensor.water_heating_temperature",
    },
    "nominal_power": 3500,
    "sg_ready": "switch.sg_ready"
}

@pytest.mark.asyncio
async def test_init_heatpump(session_storage: SessionStorage, state_repository: StatesRepository) -> None:
    """Test initilaizing a heat pump."""

    # session_storage = SessionStorageMock()
    heat_pump = HeatPumpDevice(HEATPUMP_CONFIG, session_storage)
    assert heat_pump.icon == "mdi-heat-pump"

    await heat_pump.update_state(state_repository, 0.5)

    assert heat_pump.consumed_energy == 123
    assert heat_pump.consumed_solar_energy == 61.5
    assert heat_pump.attributes == {'state': '123', 'actual_temperature': '123.0 °C'}

@pytest.mark.asyncio
async def test_init_sgready_heatpump(session_storage: SessionStorage, state_repository: StatesRepository) -> None:
    """Test initilaizing a sg ready heat pump."""

    # session_storage = SessionStorageMock()
    heat_pump = SGReadyHeatPumpDevice(SG_READY_CONFIG, session_storage)
    assert heat_pump.icon == "mdi-heat-pump"

    await heat_pump.update_state(state_repository, 0.5)

    assert heat_pump.consumed_energy == 246
    assert heat_pump.consumed_solar_energy == 123
    assert heat_pump.attributes == {'state': "off", 'heating_actual_temperature': '123.0 °C', 'water_heating_actual_temperature': '123.0 °C', 'heatpump_state': 'off'}
