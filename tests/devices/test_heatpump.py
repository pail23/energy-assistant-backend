"""Tests for the heat pumpts."""

import uuid

import pytest

from energy_assistant.devices import Session, SessionStorage
from energy_assistant.devices.heat_pump import SGReadyHeatPumpDevice


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
async def test_init_sgready_heatpump() -> None:
    """Test initilaizing a sg ready heat pump."""

    session_storage = SessionStorageMock()
    heat_pump = SGReadyHeatPumpDevice(SG_READY_CONFIG, session_storage)
    assert heat_pump.icon == "mdi-heat-pump"
