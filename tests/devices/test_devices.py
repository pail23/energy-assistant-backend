"""Tests for the devices."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from energy_assistant.devices import EnergyIntegrator, PowerModes
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant_device import HomeassistantDevice
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.models.device import Device, DeviceMeasurement
from energy_assistant.models.home import HomeMeasurement
from energy_assistant.settings import settings
from energy_assistant.storage.config import ConfigStorage
from energy_assistant.storage.storage import Database, session_storage


async def setup_data(session: AsyncSession) -> None:
    """Set up the data in the database."""

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
        solar_produced_energy = 300 + m
        grid_exported_energy = 200 + m
        grid_imported_energy = 100 + m
        home_measurement = HomeMeasurement(
            name="my home",
            measurement_date=d,
            solar_produced_energy=solar_produced_energy,
            grid_imported_energy=grid_imported_energy,
            grid_exported_energy=grid_exported_energy,
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


@pytest.mark.asyncio()
async def test_load(session: AsyncSession, device_type_registry: DeviceTypeRegistry) -> None:
    """Test the loading of the devices."""
    await setup_data(session)
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config.delete_config_file()

    await config.initialize(Path(__file__).parent / "../storage/config.yaml")

    home = Home(
        config,
        session_storage,
        device_type_registry,
    )
    device_id = uuid.UUID("1a8ac2d6-5695-427a-a3c5-ef567b34e5ec")  # Device 1
    config.devices.add_device(device_id)
    device = HomeassistantDevice(
        device_id,
        session_storage,
        config.devices,
        device_type_registry,
    )
    device.configure(
        {
            "name": "Device 1",
            "power": "power_id",
            "energy": "energy_id",
            "output": "output_id",
            "icon": "mdi-home",
        }
    )
    home.add_device(device)
    db = Database()
    home_measurement = await HomeMeasurement.read_last(session, True)
    assert home_measurement is not None
    await db.restore_home_state(home, session)
    assert home.consumed_energy == 202
    assert home.consumed_solar_energy == 100
    assert home.devices[1].consumed_solar_energy == 2
    assert home.devices[1].consumed_energy == 4

    assert True
