"""Storage of the Home state including the connected devices."""

import logging
import uuid
from datetime import UTC, datetime, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from energy_assistant.db import get_session
from energy_assistant.devices import PowerModes, Session, SessionStorage
from energy_assistant.devices.home import Home
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.devices.utility_meter import UtilityMeter
from energy_assistant.models.device import (
    Device as DeviceDTO,
)
from energy_assistant.models.device import (
    DeviceMeasurement,
)
from energy_assistant.models.device import (
    UtilityMeter as UtilityMeterDTO,
)
from energy_assistant.models.home import HomeMeasurement
from energy_assistant.models.sessionlog import SessionLogEntry

from ..constants import ROOT_LOGGER_NAME

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
                        home_measurement.solar_produced_energy,
                        home_measurement.grid_imported_energy,
                        home_measurement.grid_exported_energy,
                    )

                    snapshot_measurement = await HomeMeasurement.read_before_date(
                        session,
                        home_measurement.measurement_date,
                        True,
                    )
                    if snapshot_measurement is None:
                        snapshot_measurement = home_measurement
                    home.set_snapshot(
                        snapshot_measurement.solar_produced_energy,
                        snapshot_measurement.grid_imported_energy,
                        snapshot_measurement.grid_exported_energy,
                    )
                    for device in home.devices:
                        device_measurement = home_measurement.get_device_measurement(device.id)
                        if device_measurement is not None:
                            device.restore_state(
                                device_measurement.solar_consumed_energy,
                                device_measurement.consumed_energy,
                            )
                        device_measurement = snapshot_measurement.get_device_measurement(device.id)
                        if device_measurement is not None:
                            device.set_snapshot(
                                device_measurement.solar_consumed_energy,
                                device_measurement.consumed_energy,
                            )
                await self.restore_utility_meters(session, home)
            except Exception:
                LOGGER.exception("Error while restoring state of home")

    async def restore_utility_meters(self, session: AsyncSession, home: Home) -> None:
        """Restore the utility meters."""
        for device in home.devices:
            for utility_meter in device._utility_meters:
                utility_meter_dto = await UtilityMeterDTO.read_by_name(session, utility_meter.name, device.id)
                if utility_meter_dto is not None:
                    utility_meter.restore_last_meter_value(utility_meter_dto.last_meter_value)

    async def store_home_state(self, home: Home, session: AsyncSession, time_zone: tzinfo) -> None:
        """Store the state of the home including all devices."""
        today = datetime.now(tz=time_zone).date()
        try:
            home_measurement = await HomeMeasurement.read_by_date(session, today, True)
            if home_measurement is None:
                home_measurement = await HomeMeasurement.create(
                    session,
                    name=home.name,
                    measurement_date=today,
                    solar_produced_energy=home.produced_solar_energy,
                    grid_imported_energy=home.grid_imported_energy,
                    grid_exported_energy=home.grid_exported_energy,
                    device_measurements=[],
                )
                for device in home.devices:
                    device_dto = await DeviceDTO.read_by_id(session, device.id)
                    if device_dto is not None:
                        await DeviceMeasurement.create(
                            session,
                            home_measurement=home_measurement,
                            consumed_energy=device.consumed_energy,
                            solar_consumed_energy=device.consumed_solar_energy,
                            device=device_dto,
                        )

            else:
                await home_measurement.update(
                    session,
                    name=home.name,
                    measurement_date=today,
                    solar_produced_energy=home.produced_solar_energy,
                    grid_imported_energy=home.grid_imported_energy,
                    grid_exported_energy=home.grid_exported_energy,
                )
                for device in home.devices:
                    device_measurement = home_measurement.get_device_measurement(device.id)
                    if device_measurement is not None:
                        device_dto = await DeviceDTO.read_by_id(session, device.id)
                        if device_dto is not None:
                            await device_measurement.update(
                                session,
                                home_measurement=home_measurement,
                                consumed_energy=device.consumed_energy,
                                solar_consumed_energy=device.consumed_solar_energy,
                                device=device_dto,
                            )
            for device in home.devices:
                for utility_meter in device._utility_meters:
                    await self.create_or_update_utility_meter(session, device.id, utility_meter)
            await session.flush()
            await session.commit()
        except Exception:
            LOGGER.exception("Error while storing state of home")

    async def update_devices(
        self,
        home: Home,
        session: AsyncSession,
        session_storage: SessionStorage,
        device_type_registry: DeviceTypeRegistry,
    ) -> None:
        """Update the devices table in the db based on the configuration."""
        for device in home.devices:
            try:
                device_dto = await DeviceDTO.read_by_id(session, device.id)
                if device_dto is not None:
                    if device_dto.power_mode is not None:
                        device.set_power_mode(PowerModes[device_dto.power_mode.upper()])
                    await device_dto.update(
                        session,
                        device.name,
                        device.icon,
                        device.power_mode,
                        device.type,
                        device_dto.get_config(),
                    )
                else:
                    await DeviceDTO.create(
                        session,
                        device.id,
                        device.name,
                        device.icon,
                        device.power_mode,
                        device.type,
                        device.config,
                    )
                await session.flush()
                await session.commit()

            except Exception:
                LOGGER.exception("Error while udpateing the devices of home")
        all_devices = DeviceDTO.read_all(session)
        async for device_dto in all_devices:
            if home.get_device(device_dto.id) is None and device_dto.type is not None:
                home.create_device(device_dto.type, device_dto.get_config(), session_storage, device_type_registry)

    async def create_or_update_utility_meter(
        self,
        session: AsyncSession,
        device_id: uuid.UUID,
        utility_meter: UtilityMeter,
    ) -> None:
        """Create or update a utility meter for a given device."""
        utility_meter_dto = await UtilityMeterDTO.read_by_name(session, utility_meter.name, device_id)
        if utility_meter_dto is None:
            await UtilityMeterDTO.create(session, device_id, utility_meter.name, utility_meter.last_meter_value)
        else:
            await utility_meter_dto.update(session, device_id, utility_meter.name, utility_meter.last_meter_value)


class DbSessionStorage(SessionStorage):
    """Session storage in the database."""

    async def start_session(
        self,
        device_id: uuid.UUID,
        text: str,
        solar_consumed_energy: float,
        consumed_energy: float,
    ) -> Session:
        """Start a new session."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.create(
                session,
                text,
                device_id,
                datetime.now(UTC),
                solar_consumed_energy,
                consumed_energy,
                datetime.now(UTC),
                solar_consumed_energy,
                consumed_energy,
            )
            return Session(entry.id, entry.start, solar_consumed_energy, consumed_energy)

    async def update_session(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.read_by_id(session, id)
            if entry is not None:
                await entry.update(
                    session,
                    entry.text,
                    entry.device_id,
                    entry.start,
                    entry.start_solar_consumed_energy,
                    entry.start_consumed_energy,
                    datetime.now(UTC),
                    solar_consumed_energy,
                    consumed_energy,
                )

    async def update_session_energy(self, id: int, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update the session with the given id."""
        async_session = await get_async_session()
        async with async_session.begin() as session:
            entry = await SessionLogEntry.read_by_id(session, id)
            if entry is not None:
                await entry.update(
                    session,
                    entry.text,
                    entry.device_id,
                    entry.start,
                    entry.start_solar_consumed_energy,
                    entry.start_consumed_energy,
                    entry.end,
                    solar_consumed_energy,
                    consumed_energy,
                )


session_storage = DbSessionStorage()
