"""Data model and schema classes for a device measurement."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, AsyncIterator
import uuid

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship, selectinload

if TYPE_CHECKING:
    from .home import HomeMeasurement

from .base import Base
from .sessionlog import SessionLogEntry


class Device(Base):
    """Data model for a device."""

    __tablename__ = "devices"

    id : Mapped[uuid.UUID] = mapped_column("id", nullable=False, unique=True, primary_key=True)
    name: Mapped[str]
    icon: Mapped[str]

    device_measurements: Mapped[list[DeviceMeasurement]] = relationship(
        "DeviceMeasurement",
        back_populates="device",
        order_by="DeviceMeasurement.id",
        cascade="save-update, merge, refresh-expire, expunge, delete, delete-orphan",
    )

    session_log_entries: Mapped[list[SessionLogEntry]] = relationship(
        "SessionLogEntry",
        back_populates="device",
        order_by="SessionLogEntry.id",
        cascade="save-update, merge, refresh-expire, expunge, delete, delete-orphan",
    )

    @classmethod
    async def read_all(cls, session: AsyncSession, include_device_measurements: bool = False) -> AsyncIterator[Device]:
        """Read all devices."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(
        cls, session: AsyncSession, id: uuid.UUID, include_device_measurements: bool = False
    ) -> Device | None:
        """Read a device by id."""
        stmt = select(cls).where(cls.id == id)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.id))


    @classmethod
    async def create(cls, session: AsyncSession, id: uuid.UUID, name: str, icon: str) -> Device:
        """Create a device."""
        device = Device(
            id = id,
            name=name,
            icon = icon
        )
        session.add(device)
        await session.flush()
        return device

    async def update(self, session: AsyncSession, name: str, icon: str, power_mode: str) -> None:
        """Update a device."""
        self.name = name
        self.icon = icon
        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, device: Device) -> None:
        """Delete a device."""
        await session.delete(device)
        await session.flush()




class DeviceMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "DeviceMeasurement"

    id: Mapped[int] = mapped_column(
        "id", autoincrement=True, nullable=False, unique=True, primary_key=True)
    # TODO: drop this column
    name: Mapped[str]
    consumed_energy: Mapped[float]
    solar_consumed_energy: Mapped[float]

    home_measurement_id: Mapped[int] = mapped_column(
        "home_measurement_id", ForeignKey("HomeMeasurement.id"), nullable=False
    )

    home_measurement: Mapped[HomeMeasurement] = relationship(
        "HomeMeasurement", back_populates="device_measurements")


    device_id: Mapped[uuid.UUID] = mapped_column(
        "device_id", ForeignKey("devices.id"), nullable=False
    )

    device: Mapped[Device] = relationship(
        "Device", back_populates="device_measurements")

    @hybrid_property
    def measurement_date(self) -> datetime.date:
        """Date of a device measurement."""
        return self.home_measurement.measurement_date

    @classmethod
    async def read_all(cls, session: AsyncSession) -> AsyncIterator[DeviceMeasurement]:
        """Read all device measurements."""
        stmt = select(cls).options(joinedload(
            cls.home_measurement, innerjoin=True)) #TODO: Remove this comment .options(joinedload(cls.device, innerjoin=True))
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(
            cls, session: AsyncSession, measurement_id: int) -> DeviceMeasurement | None:
        """Read a device measurements by id."""
        stmt = select(cls).where(cls.id == measurement_id).options(
            joinedload(cls.home_measurement))
        return await session.scalar(stmt.order_by(cls.id))

    @classmethod
    async def read_by_device_id(
            cls, session: AsyncSession,  device_id: uuid.UUID) -> AsyncIterator[DeviceMeasurement]:
        """Read a device measurements by id."""
        stmt = select(cls).where(cls.device_id == device_id).options(
            joinedload(cls.home_measurement))
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_ids(cls, session: AsyncSession, measurement_ids: list[int]) -> AsyncIterator[DeviceMeasurement]:
        """Read the device measurements by within a set of ids."""
        stmt = (
            select(cls)
            .where(cls.id.in_(measurement_ids))  # type: ignore
            .options(joinedload(cls.home_measurement))
        )
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def create(cls, session: AsyncSession, home_measurement: HomeMeasurement, name: str, solar_consumed_energy: float, consumed_energy: float, device: Device) -> DeviceMeasurement:
        """Create a device measurement."""

        measurement = DeviceMeasurement(
            name=name,
            home_measurement_id=home_measurement.id,
            solar_consumed_energy=solar_consumed_energy,
            consumed_energy=consumed_energy,
            device_id = device.id
        )
        session.add(measurement)
        await session.flush()
        # To fetch home measurement
        new = await cls.read_by_id(session, measurement.id)
        if not new:
            raise RuntimeError()
        return new

    async def update(self, session: AsyncSession, home_measurement: HomeMeasurement, name: str, solar_consumed_energy: float, consumed_energy: float, device: Device) -> None:
        """Update a device measurement."""

        self.home_measurement_id = home_measurement.id
        self.name = name
        self.solar_consumed_energy = solar_consumed_energy
        self.consumed_energy = consumed_energy
        self.device_id = device.id

        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, measurement: DeviceMeasurement) -> None:
        """Delete a device measurement."""
        await session.delete(measurement)
        await session.flush()
