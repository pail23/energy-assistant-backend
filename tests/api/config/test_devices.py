"""Tests for the configuration api."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from energy_assistant.devices import PowerModes
from energy_assistant.models.device import Device, DeviceMeasurement
from energy_assistant.models.home import HomeMeasurement
from energy_assistant.models.sessionlog import SessionLogEntry

time_zone = ZoneInfo("Europe/Berlin")

DEVICE_ID = uuid.UUID("1a8ac2d6-5695-427a-a3c5-ef567b34e5ec")


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""

    device = Device(
        id=DEVICE_ID,
        name="Device 1",
        icon="mdi-home",
        power_mode=PowerModes.DEVICE_CONTROLLED,
    )
    session.add(device)
    await session.flush()

    entry1 = SessionLogEntry(
        text="Test log entry",
        device_id=device.id,
        start=datetime(2023, 1, 9, 10, 22, tzinfo=time_zone),
        start_solar_consumed_energy=100,
        start_consumed_energy=200,
        end=datetime(2023, 1, 9, 10, 30, tzinfo=time_zone),
        end_solar_consumed_energy=120,
        end_consumed_energy=240,
    )
    session.add(entry1)
    await session.flush()
    entry2 = SessionLogEntry(
        text="Test log entry",
        device_id=device.id,
        start=datetime(2023, 1, 10, 10, 22, tzinfo=time_zone),
        start_solar_consumed_energy=100,
        start_consumed_energy=200,
        end=datetime(2023, 1, 10, 10, 30, tzinfo=time_zone),
        end_solar_consumed_energy=130,
        end_consumed_energy=245,
    )
    session.add(entry2)
    await session.flush()

    dates = [date(2023, 1, 9), date(2023, 1, 10), date(2023, 1, 11)]
    for m, d in enumerate(dates):
        home_measurement = HomeMeasurement(
            name="my home",
            measurement_date=d,
            solar_produced_energy=300 + m,
            grid_imported_energy=100 + m,
            grid_exported_energy=200 + m,
            device_measurements=[],
        )
        session.add(home_measurement)
        await session.flush()
        device_measurement = DeviceMeasurement(
            home_measurement_id=home_measurement.id,
            solar_consumed_energy=m * 0.5 + 2,
            consumed_energy=m + 2,
            device_id=device.id,
        )
        session.add(device_measurement)
        await session.flush()

    await session.commit()


@pytest.mark.asyncio()
async def test_device_config_read_all(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all devices."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/config",
    )
    assert response.status_code == 200
    assert response.json() == {
        "config": {
            "energy_assistant": {
                "mqtt": {},
                "homeassistant": {},
                "home": {
                    "name": "my home",
                    "solar_power": "sensor.solar_power",
                    "solar_energy": "sensor.solar_energy",
                    "grid_supply_power": "sensor.grid_power",
                    "imported_energy": "sensor.energy_imported",
                    "exported_energy": "sensor.energyexported",
                    "disable_device_control": True,
                },
                "devices": [
                    {
                        "name": "Test Device",
                        "id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                        "type": "homeassistant",
                        "power": "sensor.device_power",
                        "energy": {"value": "sensor.device_energy", "scale": 0.001},
                        "store_sessions": True,
                        "output": "switch.device_relay_1",
                        "nominal_power": 800,
                        "nominal_duration": 7200,
                        "constant": True,
                    }
                ],
            },
            "home_assistant": {},
            "emhass": {},
        }
    }


@pytest.mark.asyncio()
async def test_device_config_read(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all devices."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        f"/api/config/device/{DEVICE_ID}",
    )
    assert response.status_code == 200
    assert response.json() == {
        "config": {
            "name": "Test Device",
            "id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
            "type": "homeassistant",
            "power": "sensor.device_power",
            "energy": {"value": "sensor.device_energy", "scale": 0.001},
            "store_sessions": True,
            "output": "switch.device_relay_1",
            "nominal_power": 800,
            "nominal_duration": 7200,
            "constant": True,
        }
    }


@pytest.mark.asyncio()
async def test_device_control(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all devices."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get("/api/config/device_control")
    assert response.status_code == 200
    assert response.json() == {"disable_device_control": True}

    response = await ac.put("/api/config/device_control?disable_device_control=false")
    assert response.status_code == 200
    assert response.json() == {"disable_device_control": False}

    response = await ac.get("/api/config/device_control")
    assert response.status_code == 200
    assert response.json() == {"disable_device_control": False}
