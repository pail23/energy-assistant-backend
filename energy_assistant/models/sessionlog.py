"""Data model and schema classes for a session logs."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .device import Device

from .base import Base


class SessionLogEntry(Base):
    """Data model for a session log entry."""

    __tablename__ = "session_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str]

    device_id: Mapped[uuid.UUID] = mapped_column("device_id", ForeignKey("devices.id"), nullable=False)

    device: Mapped[Device] = relationship("Device", back_populates="session_log_entries")

    start: Mapped[datetime]
    end: Mapped[datetime]

    start_consumed_energy: Mapped[float]
    start_solar_consumed_energy: Mapped[float]

    end_consumed_energy: Mapped[float]
    end_solar_consumed_energy: Mapped[float]

    @classmethod
    async def read_all(cls, session: AsyncSession) -> AsyncIterator[SessionLogEntry]:
        """Read all session log entries."""
        stmt = select(cls)
        stream = await session.stream_scalars(stmt.order_by(cls.start.desc()))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_device_id(cls, session: AsyncSession, device_id: uuid.UUID) -> AsyncIterator[SessionLogEntry]:
        """Read all session log entries."""
        stmt = select(cls).where(cls.device_id == device_id)
        stream = await session.stream_scalars(stmt.order_by(cls.start.desc()))
        async for row in stream:
            yield row

    @classmethod
    async def read_by_id(cls, session: AsyncSession, id: int) -> SessionLogEntry | None:
        """Read a session log entry by id."""
        stmt = select(cls).where(cls.id == id)
        return await session.scalar(stmt.order_by(cls.id))

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        text: str,
        device_id: uuid.UUID,
        start: datetime,
        start_solar_consumed_energy: float,
        start_consumed_energy: float,
        end: datetime,
        end_solar_consumed_energy: float,
        end_consumed_energy: float,
    ) -> SessionLogEntry:
        """Create a session log entry."""
        device = SessionLogEntry(
            text=text,
            device_id=device_id,
            start=start,
            start_solar_consumed_energy=start_solar_consumed_energy,
            start_consumed_energy=start_consumed_energy,
            end=end,
            end_solar_consumed_energy=end_solar_consumed_energy,
            end_consumed_energy=end_consumed_energy,
        )
        session.add(device)
        await session.flush()
        return device

    async def update(
        self,
        session: AsyncSession,
        text: str,
        device_id: uuid.UUID,
        start: datetime,
        start_solar_consumed_energy: float,
        start_consumed_energy: float,
        end: datetime,
        end_solar_consumed_energy: float,
        end_consumed_energy: float,
    ) -> None:
        """Update a session log entry."""
        self.text = text
        self.device_id = device_id
        self.start = start
        self.start_solar_consumed_energy = start_solar_consumed_energy
        self.start_consumed_energy = start_consumed_energy
        self.end = end
        self.end_solar_consumed_energy = end_solar_consumed_energy
        self.end_consumed_energy = end_consumed_energy
        await session.flush()

    @classmethod
    async def delete(cls, session: AsyncSession, session_log_entry: SessionLogEntry) -> None:
        """Delete a session log entry."""
        await session.delete(session_log_entry)
        await session.flush()
