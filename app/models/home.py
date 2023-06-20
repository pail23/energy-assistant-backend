"""Data model and schema classes for a home measurement."""

from __future__ import annotations

from datetime import date
from typing import AsyncIterator, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from .base import Base


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
    measurement_date: Mapped[date] = mapped_column("date")

    device_measurements: Mapped[list[DeviceMeasurement]] = relationship(
        "DeviceMeasurement",
        back_populates="home_measurement",
        order_by="DeviceMeasurement.id",
        cascade="save-update, merge, refresh-expire, expunge, delete, delete-orphan",
    )

    @classmethod
    async def read_all(cls, session: AsyncSession, include_device_measurements: bool) -> AsyncIterator[HomeMeasurement]:
        """Read all home measurements."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(
        cls, session: AsyncSession, HomeMeasurement_id: int, include_device_measurements: bool = False
    ) -> Optional[HomeMeasurement]:
        """Read a home measurements by id."""
        stmt = select(cls).where(cls.id == HomeMeasurement_id)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.id))

    @classmethod
    async def read_last(
            cls, session: AsyncSession, include_device_measurements: bool = False) -> Optional[HomeMeasurement]:
        """Read last home measurement."""
        stmt = select(cls)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def read_by_date(
            cls, session: AsyncSession, measurement_date: date, include_device_measurements: bool = False) -> Optional[HomeMeasurement]:
        """Read last home measurement by date."""
        stmt = select(cls).where(
            cls.measurement_date==measurement_date)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def read_before_date(
            cls, session: AsyncSession, measurement_date: date, include_device_measurements: bool = False) -> Optional[HomeMeasurement]:
        """Read last home measurement by date."""
        stmt = select(cls).where(
            cls.measurement_date<measurement_date)
        if include_device_measurements:
            stmt = stmt.options(selectinload(cls.device_measurements))
        return await session.scalar(stmt.order_by(cls.measurement_date.desc()).limit(1))

    @classmethod
    async def create(cls, session: AsyncSession, name: str, solar_consumed_energy: float, consumed_energy: float, solar_produced_energy: float, grid_imported_energy: float, grid_exported_energy: float, measurement_date: date, device_measurements: list[DeviceMeasurement]) -> HomeMeasurement:
        """Create a home measurement."""
        home_measurement = HomeMeasurement(
            name=name,
            solar_consumed_energy=solar_consumed_energy,
            consumed_energy=consumed_energy,
            solar_produced_energy=solar_produced_energy,
            grid_imported_energy=grid_imported_energy,
            grid_exported_energy=grid_exported_energy,
            measurement_date=measurement_date,
            device_measurements=device_measurements
        )
        session.add(home_measurement)
        await session.flush()
        # To fetch device measurements
        new = await cls.read_by_id(session, home_measurement.id, include_device_measurements=True)
        if not new:
            raise RuntimeError()
        return new

    async def update(self, session: AsyncSession, name: str, solar_consumed_energy: float, consumed_energy: float, solar_produced_energy: float, grid_imported_energy: float, grid_exported_energy: float, measurement_date: date) -> None:
        """Update a home measurement."""
        self.name = name
        self.solar_consumed_energy = solar_consumed_energy
        self.consumed_energy = consumed_energy
        self.solar_produced_energy = solar_produced_energy
        self.grid_imported_energy = grid_imported_energy
        self.grid_exported_energy = grid_exported_energy
        self.measurement_date = measurement_date
        # self.device_measurements = device_measurements
        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, HomeMeasurement: HomeMeasurement) -> None:
        """Delete a home measurement."""
        await session.delete(HomeMeasurement)
        await session.flush()


class HomeMeasurementSchema(BaseModel):
    """Schema class for a home measurement."""

    id: int
    name: str
    solar_consumed_energy: float
    consumed_energy: float
    solar_produced_energy: float
    grid_imported_energy: float
    grid_exported_energy: float
    measurement_date: date

    device_measurements: list[DeviceMeasurementSchema]

    class Config:
        """Config class for the Home Measurement Scheme."""

        orm_mode = True

from .device import DeviceMeasurement, DeviceMeasurementSchema  # noqa: E402

HomeMeasurementSchema.update_forward_refs()
