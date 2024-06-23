"""Use cases for devices."""

import uuid
from collections.abc import AsyncIterator

from energy_assistant.db import AsyncSession
from energy_assistant.models.sessionlog import SessionLogEntry

from .schema import SessionLogEntrySchema


class ReadAllLogEntries:
    """Read all devices use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read all devices use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID | None) -> AsyncIterator[SessionLogEntrySchema]:
        """Execute the read all devices use case."""
        async with self.async_session() as session:
            if device_id is not None:
                async for entry in SessionLogEntry.read_by_device_id(session, device_id):
                    yield SessionLogEntrySchema(
                        start=entry.start,
                        end=entry.end,
                        text=entry.text,
                        device_id=entry.device_id,
                        solar_consumed_energy=entry.end_solar_consumed_energy - entry.start_solar_consumed_energy,
                        consumed_energy=entry.end_consumed_energy - entry.start_consumed_energy,
                    )
            else:
                async for entry in SessionLogEntry.read_all(session):
                    yield SessionLogEntrySchema(
                        start=entry.start,
                        end=entry.end,
                        text=entry.text,
                        device_id=entry.device_id,
                        solar_consumed_energy=entry.end_solar_consumed_energy - entry.start_solar_consumed_energy,
                        consumed_energy=entry.end_consumed_energy - entry.start_consumed_energy,
                    )
