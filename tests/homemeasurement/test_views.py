"""Tests for the homemeasurement api."""
from datetime import date, datetime
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from energy_assistant.devices import PowerModes


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""
    from energy_assistant.models.device import Device, DeviceMeasurement
    from energy_assistant.models.home import HomeMeasurement
    from energy_assistant.models.sessionlog import SessionLogEntry

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
        start=datetime(2023, 1, 9, 10, 22),
        start_solar_consumed_energy=100,
        start_consumed_energy=200,
        end=datetime(2023, 1, 9, 10, 30),
        end_solar_consumed_energy=120,
        end_consumed_energy=240,
    )
    session.add(entry1)
    await session.flush()
    entry2 = SessionLogEntry(
        text="Test log entry",
        device_id=device.id,
        start=datetime(2023, 1, 10, 10, 22),
        start_solar_consumed_energy=100,
        start_consumed_energy=200,
        end=datetime(2023, 1, 10, 10, 30),
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
            consumed_energy=123 + 2 * m,
            solar_consumed_energy=120 + m,
            solar_produced_energy=150 + m,
            grid_imported_energy=1123 + m,
            grid_exported_energy=1540 + m,
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


@pytest.mark.asyncio
async def test_home_measurements_read_all(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all home_measurements."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/homemeasurements",
    )
    print(response.content)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_home_measurements_read_difference(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all home_measurements."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/history/difference?from_date=2023-01-09&to_date=2023-01-10",
    )
    assert response.status_code == 200

    assert response.json() == {
        "solar_consumed_energy": 1.0,
        "consumed_energy": 2.0,
        "solar_produced_energy": 1.0,
        "grid_imported_energy": 1.0,
        "grid_exported_energy": 1.0,
        "device_measurements": [
            {
                "device_id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                "solar_consumed_energy": 0.5,
                "consumed_energy": 1.0,
            },
            {
                "device_id": "9c0e0865-f3b0-488f-8d3f-b3b0cdda5de7",
                "solar_consumed_energy": 0.5,
                "consumed_energy": 1.0,
            },
        ],
    }


@pytest.mark.asyncio
async def test_home_measurements_read_daily(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all home_measurements."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/history/daily?from_date=2023-01-09&to_date=2023-01-10",
    )
    assert response.status_code == 200

    assert response.json() == {
        "measurements": [
            {
                "solar_consumed_energy": 0.0,
                "consumed_energy": 0.0,
                "solar_produced_energy": 0.0,
                "grid_imported_energy": 0.0,
                "grid_exported_energy": 0.0,
                "device_measurements": [
                    {
                        "device_id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                        "solar_consumed_energy": 0.0,
                        "consumed_energy": 0.0,
                    },
                    {
                        "device_id": "9c0e0865-f3b0-488f-8d3f-b3b0cdda5de7",
                        "solar_consumed_energy": 0.0,
                        "consumed_energy": 0.0,
                    },
                ],
                "measurement_date": "2023-01-09",
            },
            {
                "solar_consumed_energy": 1.0,
                "consumed_energy": 2.0,
                "solar_produced_energy": 1.0,
                "grid_imported_energy": 1.0,
                "grid_exported_energy": 1.0,
                "device_measurements": [
                    {
                        "device_id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                        "solar_consumed_energy": 0.5,
                        "consumed_energy": 1.0,
                    },
                    {
                        "device_id": "9c0e0865-f3b0-488f-8d3f-b3b0cdda5de7",
                        "solar_consumed_energy": 0.5,
                        "consumed_energy": 1.0,
                    },
                ],
                "measurement_date": "2023-01-10",
            },
        ]
    }


@pytest.mark.asyncio
async def test_session_log(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all sessions."""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/sessionlog?device_id=1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
    )
    assert response.status_code == 200

    assert response.json() == {
        "entries": [
            {
                "start": "2023-01-10T10:22:00",
                "end": "2023-01-10T10:30:00",
                "text": "Test log entry",
                "device_id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                "solar_consumed_energy": 30.0,
                "consumed_energy": 45.0,
            },
            {
                "start": "2023-01-09T10:22:00",
                "end": "2023-01-09T10:30:00",
                "text": "Test log entry",
                "device_id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
                "solar_consumed_energy": 20.0,
                "consumed_energy": 40.0,
            },
        ]
    }
