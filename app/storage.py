"""Storage of the Home state including the connected devices."""

from datetime import date
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_session
from app.devices.home import Home
from app.models.device import Device as DeviceDTO, DeviceMeasurement
from app.models.home import HomeMeasurement


async def get_async_session() -> async_sessionmaker:
    """Get a async database session."""
    return await anext(get_session())


class Database:
    """Database for storing home and devie measurement data."""

    def __init__(self) -> None:
        """Create a Database instance."""

    async def restore_home_state(self, home: Home, session: AsyncSession) -> None:
        """Restore the state of the home from the database."""
        if home is not None:
            try:
                home_measurement = await HomeMeasurement.read_last(session, True)
                if home_measurement is not None:
                    home.restore_state(
                        home_measurement.solar_consumed_energy, home_measurement.consumed_energy, home_measurement.solar_produced_energy, home_measurement.grid_imported_energy, home_measurement.grid_exported_energy)

                    snapshot_measurement = await HomeMeasurement.read_before_date(session, home_measurement.measurement_date, True)
                    if snapshot_measurement is None:
                        snapshot_measurement = home_measurement
                    home.set_snapshot(
                        snapshot_measurement.solar_consumed_energy, snapshot_measurement.consumed_energy, snapshot_measurement.solar_produced_energy, snapshot_measurement.grid_imported_energy, snapshot_measurement.grid_exported_energy)
                    for device in home.devices:
                        device_measurement = home_measurement.get_device_measurement(device.id)
                        if device_measurement is not None:
                            device.restore_state(
                                device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
                        device_measurement = snapshot_measurement.get_device_measurement(device.id)
                        if device_measurement is not None:
                            device.set_snapshot(
                                device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
            except Exception as ex:
                logging.error(
                    "Error while restoring state of home", ex)


    async def store_home_state(self, home: Home, session: AsyncSession) -> None:
        """Store the state of the home including all devices."""
        today = date.today()
        try:
            home_measurement = await HomeMeasurement.read_by_date(session, today, True)
            if home_measurement is None:
                home_measurement = await HomeMeasurement.create(session,
                    name=home.name, measurement_date=today, consumed_energy=home.consumed_energy, solar_consumed_energy=home.consumed_solar_energy, solar_produced_energy=home.produced_solar_energy, grid_imported_energy=home.grid_imported_energy, grid_exported_energy=home.grid_exported_energy, device_measurements=[])
                for device in home.devices:
                    device_dto = await DeviceDTO.read_by_id(session, device.id)
                    if device_dto is not None:
                        await DeviceMeasurement.create(session, home_measurement=home_measurement, name=device.name, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy, device=device_dto)

            else:
                await home_measurement.update(session, name=home.name, measurement_date=today, consumed_energy=home.consumed_energy, solar_consumed_energy=home.consumed_solar_energy, solar_produced_energy=home.produced_solar_energy, grid_imported_energy=home.grid_imported_energy, grid_exported_energy=home.grid_exported_energy)
                for device in home.devices:
                    device_measurement = home_measurement.get_device_measurement(device.id)
                    if device_measurement is not None:
                        device_dto = await DeviceDTO.read_by_id(session, device.id)
                        if device_dto is not None:
                            await device_measurement.update(session, home_measurement=home_measurement, name=device.name, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy, device=device_dto)
            await session.flush()
            await session.commit()
        except Exception as ex:
            logging.error(
                "Error while storing state of home", ex)


    async def update_devices(self, home: Home, session: AsyncSession) -> None:
        """Update the devices table in the db based on the configuration."""
        for device in home.devices:
            try:
                device_dto = await DeviceDTO.read_by_id(session, device.id)
                if device_dto is not None:
                    await device_dto.update(session, device.name, device.icon)
                else:
                    await DeviceDTO.create(session, device.id, device.name, device.icon)
                await session.flush()
                await session.commit()

            except Exception as ex:
                logging.error(
                    "Error while udpateing the devices of home", ex)
