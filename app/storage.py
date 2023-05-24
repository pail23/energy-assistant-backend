from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.future import select

from datetime import date, datetime, timedelta
import logging

from devices import Device
from devices.homeassistant import Home

class Base(AsyncAttrs, DeclarativeBase):
    pass

class DeviceMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "DeviceMeasurement"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    solar_energy : Mapped[float]
    solar_consumed_energy : Mapped[float]
    date : Mapped[date]

class Database:
    def __init__(self, sql_echo: bool = False):
        self.sql_echo = sql_echo

    async def create_db_engine(self):
        engine = create_async_engine(
            "sqlite+aiosqlite:///energy_assistant.db",
            echo=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def restore_measurement(self, device: Device):
        try:
            async with self._async_session() as session:
                statement = select(DeviceMeasurement).filter_by(name=device.name).order_by(DeviceMeasurement.date.desc()).limit(1)
                result = await session.execute(statement)
                device_measurement = result.scalar() 
                if device_measurement is not None:
                    device.restore_state(device_measurement.solar_consumed_energy, device_measurement.solar_energy)
        except Exception as ex:
            logging.error(f"Error while restoring state of device {device.name}", ex)

    async def restore_snapshot(self, device: Device):
        try:
            yesterday = date.today() - timedelta(days=1)
            async with self._async_session() as session:
                statement = select(DeviceMeasurement).filter_by(name=device.name, date=yesterday).limit(1)
                result = await session.execute(statement)
                device_measurement = result.scalar() 
                if device_measurement is not None:
                    device.set_snapshot(device_measurement.solar_consumed_energy, device_measurement.solar_energy)
        except Exception as ex:
            logging.error(f"Error while restoring state of device {device.name}", ex)

    async def restore_home_state(self, home: Home):
        if home is not None:
            await self.restore_measurement(home)
            await self.restore_snapshot(home)
            for device in home.devices:
                await self.restore_measurement(device)
                await self.restore_measurement(device)

    async def store_measurement(self, session, device: Device):
        today = date.today()
        try:
            statement = select(DeviceMeasurement).filter_by(name=device.name, date=today)
            result = await session.execute(statement)
            device_measurement = result.scalar_one_or_none()
            if device_measurement is None:
                device_measurement = DeviceMeasurement(name = device.name, date=today)
                session.add(device_measurement)
            device_measurement.solar_energy = device.consumed_energy
            device_measurement.solar_consumed_energy = device.consumed_solar_energy
        except Exception as ex:
            logging.error(f"Error while storing state of device {device.name}", ex)


    async def store_home_state(self, home: Home):
        async with self._async_session() as session:
            async with session.begin():
                await self.store_measurement(session, home)

                for device in home.devices:
                    await self.store_measurement(session, device)
            await session.commit()
