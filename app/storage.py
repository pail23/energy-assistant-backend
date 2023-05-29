"""Storage of the Home state including the connected devices."""

from datetime import date, timedelta
import logging

from devices import Device
from devices.homeassistant import Home
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for the ORM models."""

    pass


class DeviceMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "DeviceMeasurement"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    consumed_energy: Mapped[float]
    solar_consumed_energy: Mapped[float]
    date: Mapped[date]


class HomeMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "HomeMeasurement"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    consumed_energy: Mapped[float]
    solar_consumed_energy: Mapped[float]
    solar_produced_energy: Mapped[float]
    grid_imported_energy: Mapped[float]
    grid_exported_energy: Mapped[float]
    date: Mapped[date]


class Database:
    """Database for storing home and devie measurement data."""

    def __init__(self, sql_echo: bool = False):
        """Create a Database instance."""
        self.sql_echo = sql_echo

    async def create_db_engine(self):
        """Create the database."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///energy_assistant.db",
            echo=self.sql_echo,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._async_session = async_sessionmaker(
            engine, expire_on_commit=False)

    async def restore_measurement(self, device: Device):
        """Restore a previously stored measurement."""
        try:
            async with self._async_session() as session:
                statement = select(DeviceMeasurement).filter_by(
                    name=device.name).order_by(DeviceMeasurement.date.desc()).limit(1)
                result = await session.execute(statement)
                device_measurement = result.scalar()
                if device_measurement is not None:
                    device.restore_state(
                        device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
        except Exception as ex:
            logging.error(
                f"Error while restoring state of device {device.name}", ex)

    async def restore_snapshot(self, device: Device):
        """Restore a previously stored snapshot."""
        try:
            yesterday = date.today() - timedelta(days=1)
            async with self._async_session() as session:
                statement = select(DeviceMeasurement).filter_by(
                    name=device.name, date=yesterday).limit(1)
                result = await session.execute(statement)
                device_measurement = result.scalar()
                if device_measurement is not None:
                    device.set_snapshot(
                        device_measurement.solar_consumed_energy, device_measurement.consumed_energy)
        except Exception as ex:
            logging.error(
                f"Error while restoring state of device {device.name}", ex)


    async def restore_home_state(self, home: Home):
        """Restore the state of the home from the database."""
        if home is not None:
            try:
                async with self._async_session() as session:
                    statement = select(HomeMeasurement).order_by(HomeMeasurement.date.desc()).limit(1)
                    result = await session.execute(statement)
                    home_measurement = result.scalar()
                    if home_measurement is not None:
                        home.restore_state(
                            home_measurement.solar_consumed_energy, home_measurement.consumed_energy, home_measurement.solar_produced_energy, home_measurement.grid_imported_energy, home_measurement.grid_exported_energy)

                    yesterday = date.today() - timedelta(days=1)
                    statement = select(HomeMeasurement).filter_by(
                        date=yesterday).limit(1)
                    result = await session.execute(statement)
                    snapshot_measurement = result.scalar()
                    if snapshot_measurement is not None:
                        home.set_snapshot(
                            snapshot_measurement.solar_consumed_energy, snapshot_measurement.consumed_energy, snapshot_measurement.solar_produced_energy, snapshot_measurement.grid_imported_energy, snapshot_measurement.grid_exported_energy)
                    elif home_measurement is not None:
                        home.set_snapshot(
                            home_measurement.solar_consumed_energy, home_measurement.consumed_energy, home_measurement.solar_produced_energy, home_measurement.grid_imported_energy, home_measurement.grid_exported_energy)

            except Exception as ex:
                logging.error(
                    "Error while restoring state of home", ex)

            for device in home.devices:
                await self.restore_measurement(device)
                await self.restore_snapshot(device)

    async def store_measurement(self, session, device: Device):
        """Store a measurement from a device."""
        today = date.today()
        try:
            statement = select(DeviceMeasurement).filter_by(
                name=device.name, date=today)
            result = await session.execute(statement)
            device_measurement = result.scalar_one_or_none()
            if device_measurement is None:
                device_measurement = DeviceMeasurement(
                    name=device.name, date=today)
                session.add(device_measurement)
            device_measurement.consumed_energy = device.consumed_energy
            device_measurement.solar_consumed_energy = device.consumed_solar_energy
        except Exception as ex:
            logging.error(
                f"Error while storing state of device {device.name}", ex)

    async def store_home_state(self, home: Home):
        """Store the state of the home including all devices."""
        async with self._async_session() as session:
            async with session.begin():
                today = date.today()
                try:
                    statement = select(HomeMeasurement).filter_by(date=today)
                    result = await session.execute(statement)
                    home_measurement = result.scalar_one_or_none()
                    if home_measurement is None:
                        home_measurement = HomeMeasurement(
                            name=home.name, date=today)
                        session.add(home_measurement)
                    home_measurement.consumed_energy = home.consumed_energy
                    home_measurement.solar_consumed_energy = home.consumed_solar_energy
                    home_measurement.solar_produced_energy = home.produced_solar_energy
                    home_measurement.grid_imported_energy = home.grid_imported_energy
                    home_measurement.grid_exported_energy = home.grid_exported_energy
                except Exception as ex:
                    logging.error(
                        "Error while storing state of home", ex)

                for device in home.devices:
                    await self.store_measurement(session, device)
            await session.commit()
