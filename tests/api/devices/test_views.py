"""Tests for the homemeasurement api."""

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


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""
    device = Device(
        id=uuid.UUID("1a8ac2d6-5695-427a-a3c5-ef567b34e5ec"),
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
async def test_devices_read_all(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all devices."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/devices?filter_with_session_log_enties=false",
    )
    print(response.content)
    assert response.status_code == 200


@pytest.mark.asyncio()
async def test_devices_delete(ac: AsyncClient, session: AsyncSession) -> None:
    """Delete a device."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.delete(
        "/api/devices/1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
    )
    assert response.status_code == 204

    # execute
    response = await ac.get(
        "/api/sessionlog",
    )
    assert response.status_code == 200

    assert response.json() == {"entries": []}

    response = await ac.get(
        "/api/devices/1a8ac2d6-5695-427a-a3c5-ef567b34e5ec/measurements",
    )
    print(response.content)
    assert response.status_code == 200
    assert response.json() == {"device_measurements": []}
