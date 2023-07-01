"""Use cases for devices."""
from typing import AsyncIterator
import uuid

from fastapi import HTTPException

from app.db import AsyncSession
from app.models.device import Device, DeviceSchema

from . import OTHER_DEVICE


class ReadAllDevices:
    """Read all devices use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read all devices use case."""
        self.async_session = session

    async def execute(self) -> AsyncIterator[DeviceSchema]:
        """Execute the read all devices use case."""
        async with self.async_session() as session:
            async for device in Device.read_all(session):
                yield DeviceSchema.from_orm(device)
        yield DeviceSchema(id=OTHER_DEVICE, name="Andere", icon="mdi-home")


class ReadDevice:
    """Read adevice use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read device use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID) -> DeviceSchema:
        """Execute the read device use case."""
        async with self.async_session() as session:
            device = await Device.read_by_id(session, device_id)
            if not device:
                raise HTTPException(status_code=404)
            return DeviceSchema.from_orm(device)


class DeleteDevice:
    """Delete a device use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a delete a device use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID) -> None:
        """Execute the delete a device use case."""
        async with self.async_session.begin() as session:
            device = await Device.read_by_id(session, device_id)
            if not device:
                return
            await Device.delete(session, device)
