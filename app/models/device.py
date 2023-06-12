"""Data model and schema classes for a device measurement."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, AsyncIterator, Optional

from pydantic import BaseModel
from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship

if TYPE_CHECKING:
    from .home import HomeMeasurement

from .base import Base


class DeviceMeasurement(Base):
    """Data model for a measurement."""

    __tablename__ = "DeviceMeasurement"

    id: Mapped[int] = mapped_column(
        "id", autoincrement=True, nullable=False, unique=True, primary_key=True)
    name: Mapped[str]
    consumed_energy: Mapped[float]
    solar_consumed_energy: Mapped[float]

    home_measurement_id: Mapped[int] = mapped_column(
        "home_measurement_id", ForeignKey("HomeMeasurement.id"), nullable=False
    )

    home_measurement: Mapped[HomeMeasurement] = relationship(
        "HomeMeasurement", back_populates="device_measurements")

    @hybrid_property
    def date(self) -> date:
        """Date of a device measurement."""
        return self.home_measurement.measurement_date

    @classmethod
    async def read_all(cls, session: AsyncSession) -> AsyncIterator[DeviceMeasurement]:
        """Read all device measurements."""
        stmt = select(cls).options(joinedload(
            cls.home_measurement, innerjoin=True))
        stream = await session.stream_scalars(stmt.order_by(cls.id))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(
            cls, session: AsyncSession, measurement_id: int) -> Optional[DeviceMeasurement]:
        """Read a device measurements by id."""
        stmt = select(cls).where(cls.id == measurement_id).options(
            joinedload(cls.home_measurement))
        return await session.scalar(stmt.order_by(cls.id))



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
    async def create(cls, session: AsyncSession, home_measurement: HomeMeasurement, name: str, solar_consumed_energy: float, consumed_energy: float) -> DeviceMeasurement:
        """Create a device measurement."""

        measurement = DeviceMeasurement(
            name=name,
            home_measurement_id=home_measurement.id,
            solar_consumed_energy=solar_consumed_energy,
            consumed_energy=consumed_energy
        )
        session.add(measurement)
        await session.flush()
        # To fetch home measurement
        new = await cls.read_by_id(session, measurement.id)
        if not new:
            raise RuntimeError()
        return new

    async def update(self, session: AsyncSession, home_measurement: HomeMeasurement, name: str, solar_consumed_energy: float, consumed_energy: float) -> None:
        """Update a device measurement."""

        self.home_measurement_id = home_measurement.id
        self.name = name
        self.solar_consumed_energy = solar_consumed_energy
        self.consumed_energy = consumed_energy
        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, measurement: DeviceMeasurement) -> None:
        """Delete a device measurement."""
        await session.delete(measurement)
        await session.flush()


class DeviceMeasurementSchema(BaseModel):
    """Schema class for a device measurement."""

    id: int
    name: str
    solar_consumed_energy: float
    consumed_energy: float
    home_measurement_id: int
    date: date

    class Config:
        """Config class for the Device Measurement Scheme."""

        orm_mode = True
