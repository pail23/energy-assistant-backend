"""Data model and schema classes for a home measurement."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from .base import Base

if TYPE_CHECKING:
    from .device import DeviceMeasurement


def get_consumed_energy(measurement: HomeMeasurement) -> float:
    """Get the consumed energy from a measurement."""
    return measurement.solar_produced_energy + measurement.grid_imported_energy - measurement.grid_exported_energy


def get_consumed_solar_energy(measurement: HomeMeasurement) -> float:
    """Get the consumed solar energy from a measurement."""
    return measurement.solar_produced_energy - measurement.grid_exported_energy


class HomeMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "HomeMeasurement"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    solar_produced_energy: Mapped[float]
    grid_imported_energy: Mapped[float]
    grid_exported_energy: Mapped[float]
    measurement_date: Mapped[date] = mapped_column("date")

    device_measurements: Mapped[list[DeviceMeasurement]] = relationship(
        "DeviceMeasurement",
        back_populates="home_measurement",
        order_by="DeviceMeasurement.id",
        cascade="save-update, merge, refresh-expire, expunge, delete, delete-orphan",
    )

    @property
    def consumed_energy(self) -> float:
        """Get the consumed energy from a measurement."""
        return self.solar_produced_energy + self.grid_imported_energy - self.grid_exported_energy

    @property
    def solar_consumed_energy(self) -> float:
        """Get the consumed solar energy from a measurement."""
        return self.solar_produced_energy - self.grid_exported_energy

    @classmethod
    async def read_all(cls, session: AsyncSession, include_device_measurements: bool) -> AsyncIterator[HomeMeasurement]:
        """Read all home measurements."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        stream = await session.stream_scalars(stmt.order_by(cls.measurement_date.desc()))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(
        cls,
        session: AsyncSession,
        home_measurement_id: int,
        include_device_measurements: bool = False,
    ) -> HomeMeasurement | None:
        """Read a home measurements by id."""
        stmt = select(cls).where(cls.id == home_measurement_id)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.id))

    @classmethod
    async def read_first(
        cls,
        session: AsyncSession,
        include_device_measurements: bool = False,
    ) -> HomeMeasurement | None:
        """Read last home measurement by date."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date).limit(1))

    @classmethod
    async def read_last(
        cls,
        session: AsyncSession,
        include_device_measurements: bool = False,
    ) -> HomeMeasurement | None:
        """Read last home measurement."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def read_by_date(
        cls,
        session: AsyncSession,
        measurement_date: date,
        include_device_measurements: bool = False,
    ) -> HomeMeasurement | None:
        """Read last home measurement by date."""
        stmt = select(cls).where(cls.measurement_date == measurement_date)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def read_between_dates(
        cls,
        session: AsyncSession,
        from_date: date,
        to_date: date,
        include_device_measurements: bool = False,
    ) -> AsyncIterator[HomeMeasurement]:
        """Read last home measurement by date."""
        stmt = select(cls).where(cls.measurement_date >= from_date).where(cls.measurement_date <= to_date)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        stream = await session.stream_scalars(stmt.order_by(cls.measurement_date))
        async for row in stream:
            yield row

    @classmethod
    async def read_before_date(
        cls,
        session: AsyncSession,
        measurement_date: date,
        include_device_measurements: bool = False,
    ) -> HomeMeasurement | None:
        """Read last home measurement by date."""
        stmt = select(cls).where(cls.measurement_date < measurement_date)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        name: str,
        solar_produced_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
        measurement_date: date,
        device_measurements: list[DeviceMeasurement],
    ) -> HomeMeasurement:
        """Create a home measurement."""
        home_measurement = HomeMeasurement(
            name=name,
            solar_produced_energy=solar_produced_energy,
            grid_imported_energy=grid_imported_energy,
            grid_exported_energy=grid_exported_energy,
            measurement_date=measurement_date,
            device_measurements=device_measurements,
        )
        session.add(home_measurement)
        await session.flush()
        # To fetch device measurements
        new = await cls.read_by_id(session, home_measurement.id, include_device_measurements=True)
        if not new:
            raise RuntimeError
        return new

    async def update(
        self,
        session: AsyncSession,
        name: str,
        solar_produced_energy: float,
        grid_imported_energy: float,
        grid_exported_energy: float,
        measurement_date: date,
    ) -> None:
        """Update a home measurement."""
        self.name = name
        self.solar_produced_energy = solar_produced_energy
        self.grid_imported_energy = grid_imported_energy
        self.grid_exported_energy = grid_exported_energy
        self.measurement_date = measurement_date
        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, home_measurement: HomeMeasurement) -> None:
        """Delete a home measurement."""
        await session.delete(home_measurement)
        await session.flush()

    def get_device_measurement(self, device_id: uuid.UUID) -> DeviceMeasurement | None:
        """Find the device measurement of the device with the given id."""
        for device_measurement in self.device_measurements:
            if device_measurement.device_id == device_id:
                return device_measurement
        return None
