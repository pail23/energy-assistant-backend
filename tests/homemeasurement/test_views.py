"""Tests for the homemeasurement api."""
from datetime import date
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""
    from app.models.device import Device, DeviceMeasurement
    from app.models.home import HomeMeasurement

    device = Device(id=uuid.UUID("1a8ac2d6-5695-427a-a3c5-ef567b34e5ec"), name="Device 1", icon="mdi-home")
    session.add(device)
    await session.flush()

    dates = [date(2023, 1, 9), date(2023, 1, 10), date(2023, 1, 11)]
    for m, d in enumerate(dates):
        home_measurement = HomeMeasurement(name="my home", measurement_date=d, consumed_energy=123 + m, solar_consumed_energy=120 + 0.5 * m, solar_produced_energy=150 + m, grid_imported_energy=1123 + m, grid_exported_energy=1540 + m, device_measurements=[])
        session.add(home_measurement)
        await session.flush()
        for i in range(0,3):
            device_measurement = DeviceMeasurement(name=f"Device {i}", home_measurement_id=home_measurement.id, consumed_energy=2 + 0.5 * i, solar_consumed_energy=1 + i, device_id = device.id )
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
        "/api/history/difference/2023-01-10?to_date=2023-01-09",
    )
    print(response.content)
    assert response.status_code == 200


    response = await ac.get(
        "/api/history/difference/2022-01-10?to_date=2023-01-09",
    )
    print(response.content)
    assert response.status_code == 200
