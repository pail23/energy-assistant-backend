"""Storage of the Home state including the connected devices."""

from datetime import date, timedelta
import logging

from db import create_all, get_session
from devices import Device
from devices.homeassistant import Home
from models.device import DeviceMeasurement
from models.home import HomeMeasurement


async def get_async_session():
    """Get a async database session."""
    return await anext(get_session())


class Database:
    """Database for storing home and devie measurement data."""

    def __init__(self):
        """Create a Database instance."""

    async def create_db_engine(self):
        """Create the database."""

        # TODO: migrate to alembic
        await create_all()

    async def restore_measurement(self, home_measurement: HomeMeasurement, device: Device):
        """Restore a previously stored measurement."""
        if home_measurement is not None:
            for device_measurement in home_measurement.device_measurements:
                if device_measurement.name == device.name:
                    device.restore_state(
                        device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
                    break

    async def restore_snapshot(self, home_measurement: HomeMeasurement, device: Device):
        """Restore a previously stored snapshot."""
        if home_measurement is not None:
            for device_measurement in home_measurement.device_measurements:
                if device_measurement.name == device.name:
                    device.set_snapshot(
                        device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
                    break

    async def restore_home_state(self, home: Home):
        """Restore the state of the home from the database."""
        if home is not None:
            try:
                async_session = await get_async_session()
                async with async_session.begin() as session:
                    home_measurement = await HomeMeasurement.read_last(session, True)
                    if home_measurement is not None:
                        home.restore_state(
                            home_measurement.solar_consumed_energy, home_measurement.consumed_energy, home_measurement.solar_produced_energy, home_measurement.grid_imported_energy, home_measurement.grid_exported_energy)

                    yesterday = date.today() - timedelta(days=1)
                    snapshot_measurement = await HomeMeasurement.read_by_date(session, yesterday, True)
                    if snapshot_measurement is None:
                        snapshot_measurement = home_measurement
                    if snapshot_measurement is not None:
                        home.set_snapshot(
                            snapshot_measurement.solar_consumed_energy, snapshot_measurement.consumed_energy, snapshot_measurement.solar_produced_energy, snapshot_measurement.grid_imported_energy, snapshot_measurement.grid_exported_energy)
                    for device in home.devices:
                        await self.restore_measurement(home_measurement, device)
                        await self.restore_snapshot(snapshot_measurement, device)
            except Exception as ex:
                logging.error(
                    "Error while restoring state of home", ex)


    async def store_home_state(self, home: Home):
        """Store the state of the home including all devices."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            today = date.today()
            try:
                home_measurement = await HomeMeasurement.read_by_date(session, today, True)
                if home_measurement is None:
                    home_measurement = await HomeMeasurement.create(session,
                        name=home.name, date=today, consumed_energy=home.consumed_energy, solar_consumed_energy=home.consumed_solar_energy, solar_produced_energy=home.produced_solar_energy, grid_imported_energy=home.grid_imported_energy, grid_exported_energy=home.grid_exported_energy, device_measurements=[])
                    for device in home.devices:
                        await DeviceMeasurement.create(session, home_measurement=home_measurement, name=device.name, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy)

                else:
                   await home_measurement.update(session, name=home.name, date=today, consumed_energy=home.consumed_energy, solar_consumed_energy=home.consumed_solar_energy, solar_produced_energy=home.produced_solar_energy, grid_imported_energy=home.grid_imported_energy, grid_exported_energy=home.grid_exported_energy)
                   for device in home.devices:
                        for device_measurement in home_measurement.device_measurements:
                            if device_measurement.name == device.name:
                                await device_measurement.update(session, home_measurement=home_measurement, name=device.name, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy)
                                break

            except Exception as ex:
                logging.error(
                    "Error while storing state of home", ex)
