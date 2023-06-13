import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils import ID_STRING


async def setup_data(session: AsyncSession) -> None:
    from app.models.home import HomeMeasurement
    from app.models.device import DeviceMeasurement


    yesterday = date.today() - timedelta(days=1)
    home_measurement1 = HomeMeasurement(name="HomeMeasurement 1", measurement_date=yesterday, consumed_energy=123, solar_consumed_energy=120, solar_produced_energy=150, grid_imported_energy=1123, grid_exported_energy=1540, device_measurements=[])
    home_measurement2 = HomeMeasurement(name="HomeMeasurement 2", measurement_date=date.today(), consumed_energy=123, solar_consumed_energy=120, solar_produced_energy=150, grid_imported_energy=1123, grid_exported_energy=1540, device_measurements=[])
    session.add_all([home_measurement1, home_measurement2])
    await session.flush()


    device1 = DeviceMeasurement(name="DeviceMeasurement 1", home_measurement_id=home_measurement1.id, consumed_energy=2, solar_consumed_energy=1 )
    device2 = DeviceMeasurement(name="DeviceMeasurement 2", home_measurement_id=home_measurement1.id, consumed_energy=2, solar_consumed_energy=1 )
    device3 = DeviceMeasurement(name="DeviceMeasurement 3", home_measurement_id=home_measurement2.id, consumed_energy=2, solar_consumed_energy=1 )
    session.add_all([device1, device2, device3])
    await session.flush()

    await session.commit()


@pytest.mark.asyncio
async def test_home_measurements_read_all(ac: AsyncClient, session: AsyncSession) -> None:
    """Read all home_measurements"""
    # setup
    await setup_data(session)

    # execute
    response = await ac.get(
        "/api/homemeasurements",
    )
    print(response.content)
    assert 200 == response.status_code