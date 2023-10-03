"""Storage of the Home state including the connected devices."""

from datetime import date, datetime, timezone
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_session
from app.devices import PowerModes, SessionStorage
from app.devices.home import Home
from app.models.device import Device as DeviceDTO, DeviceMeasurement
from app.models.home import HomeMeasurement
from app.models.sessionlog import SessionLogEntry

from .constants import ROOT_LOGGER_NAME

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)

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
                        device_measurement = home_measurement.get_device_measurement(
                            device.id)
                        if device_measurement is not None:
                            device.restore_state(
                                device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
                        device_measurement = snapshot_measurement.get_device_measurement(
                            device.id)
                        if device_measurement is not None:
                            device.set_snapshot(
                                device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
            except Exception as ex:
                LOGGER.error(
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
                        await DeviceMeasurement.create(session, home_measurement=home_measurement, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy, device=device_dto)

            else:
                await home_measurement.update(session, name=home.name, measurement_date=today, consumed_energy=home.consumed_energy, solar_consumed_energy=home.consumed_solar_energy, solar_produced_energy=home.produced_solar_energy, grid_imported_energy=home.grid_imported_energy, grid_exported_energy=home.grid_exported_energy)
                for device in home.devices:
                    device_measurement = home_measurement.get_device_measurement(
                        device.id)
                    if device_measurement is not None:
                        device_dto = await DeviceDTO.read_by_id(session, device.id)
                        if device_dto is not None:
                            await device_measurement.update(session, home_measurement=home_measurement, consumed_energy=device.consumed_energy, solar_consumed_energy=device.consumed_solar_energy, device=device_dto)
            await session.flush()
            await session.commit()
        except Exception as ex:
            LOGGER.error(
                "Error while storing state of home", ex)

    async def update_devices(self, home: Home, session: AsyncSession) -> None:
        """Update the devices table in the db based on the configuration."""
        for device in home.devices:
            try:
                device_dto = await DeviceDTO.read_by_id(session, device.id)
                if device_dto is not None:
                    if device_dto.power_mode is not None:
                        device.set_power_mode(PowerModes[device_dto.power_mode.upper()])
                    await device_dto.update(session, device.name, device.icon, device.power_mode)
                else:
                    await DeviceDTO.create(session, device.id, device.name, device.icon, device.power_mode)
                await session.flush()
                await session.commit()

            except Exception as ex:
                LOGGER.error(
                    "Error while udpateing the devices of home", ex)


class DbSessionStorage(SessionStorage):
    """Session storage in the database."""

    async def start_session(self, device_id: uuid.UUID,  text: str, solar_consumed_energy: float, consumed_energy: float) -> int:
        """Start a new session."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.create(session, text, device_id, datetime.now(timezone.utc), solar_consumed_energy, consumed_energy, datetime.now(timezone.utc), solar_consumed_energy, consumed_energy)
            return entry.id

    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.read_by_id(session, id)
            if entry is not None:
                await entry.update(session, entry.text, entry.device_id, entry.start, entry.start_solar_consumed_energy, entry.start_consumed_energy, datetime.now(timezone.utc),
                                   solar_consumed_energy, consumed_energy)

    async def update_session_energy(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.read_by_id(session, id)
            if entry is not None:
                await entry.update(session, entry.text, entry.device_id, entry.start, entry.start_solar_consumed_energy, entry.start_consumed_energy, entry.end,
                                   solar_consumed_energy, consumed_energy)

session_storage = DbSessionStorage()
