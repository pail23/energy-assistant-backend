"""Tests for the devices."""
from datetime import date
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from energy_assistant.devices import EnergyIntegrator, PowerModes
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import HomeassistantDevice
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.models.home import HomeMeasurement
from energy_assistant.storage import Database, session_storage


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""
    from energy_assistant.models.device import Device, DeviceMeasurement
    from energy_assistant.models.home import HomeMeasurement

    device1 = Device(
        id=uuid.UUID("1a8ac2d6-5695-427a-a3c5-ef567b34e5ec"),
        name="Device 1",
        icon="mdi-home",
        power_mode=PowerModes.DEVICE_CONTROLLED,
    )
    session.add(device1)
    device2 = Device(
        id=uuid.UUID("2a8ac2d6-5695-427a-a3c5-ef567b34e5ec"),
        name="Device 2",
        icon="mdi-home",
        power_mode=PowerModes.DEVICE_CONTROLLED,
    )
    session.add(device2)
    await session.flush()
    devices = [device1, device2]

    dates = [date(2023, 1, 9), date(2023, 1, 10), date(2023, 1, 11)]
    for m, d in enumerate(dates):
        home_measurement = HomeMeasurement(
            name="my home",
            measurement_date=d,
            consumed_energy=123 + m,
            solar_consumed_energy=120 + 0.5 * m,
            solar_produced_energy=150 + m,
            grid_imported_energy=1123 + m,
            grid_exported_energy=1540 + m,
            device_measurements=[],
        )
        session.add(home_measurement)
        await session.flush()
        for i, device in enumerate(devices):
            device_measurement = DeviceMeasurement(
                home_measurement_id=home_measurement.id,
                consumed_energy=2 + 0.5 * i + m,
                solar_consumed_energy=1 + i + 0.5 * m,
                device_id=device.id,
            )
            session.add(device_measurement)
        await session.flush()

    await session.commit()


def test_integrator() -> None:
    """Test the energy integrator."""
    integrator = EnergyIntegrator()
    integrator.restore_state(15, 20)
    integrator.add_measurement(30, 0.1)
    assert integrator.consumed_solar_energy == 16


@pytest.mark.asyncio
async def test_load(session: AsyncSession, device_type_registry: DeviceTypeRegistry) -> None:
    """Test the loading of the devices."""
    await setup_data(session)

    home = Home(
        {
            "name": "my home",
            "solar_power": "solar_power_id",
            "grid_supply_power": "grid_supply_power_id",
            "solar_energy": "solar_energy_id",
            "imported_energy": "imported_energy_id",
            "exported_energy": "exported_energy_id",
        },
        session_storage,
        device_type_registry,
    )
    device = HomeassistantDevice(
        {
            "id": "1a8ac2d6-5695-427a-a3c5-ef567b34e5ec",
            "name": "Device 1",
            "power": "power_id",
            "energy": "energy_id",
        },
        session_storage,
        device_type_registry,
    )
    home.add_device(device)
    db = Database()
    home_measurement = await HomeMeasurement.read_last(session, True)
    assert home_measurement is not None
    await db.restore_home_state(home, session)
    assert home.consumed_energy == 125
    assert home.consumed_solar_energy == 121
    assert home.devices[0].consumed_solar_energy == 2
    assert home.devices[0].consumed_energy == 4

    assert True
