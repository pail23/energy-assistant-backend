"""Use cases for devices."""
import logging
from typing import AsyncIterator
import uuid

from fastapi import HTTPException

from app.db import AsyncSession
from app.devices import PowerModes
from app.devices.home import Home
from app.models import DeviceMeasurementSchema, DeviceSchema
from app.models.device import Device, DeviceMeasurement

from . import OTHER_DEVICE


class ReadAllDevices:
    """Read all devices use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read all devices use case."""
        self.async_session = session

    async def execute(self, home: Home) -> AsyncIterator[DeviceSchema]:
        """Execute the read all devices use case."""
        async with self.async_session() as session:
            async for device in Device.read_all(session):
                result = DeviceSchema.model_validate(device)
                d = home.get_device(device.id)
                if d is not None:
                    result.supported_power_modes = list(d.supported_power_modes)
                    result.power_mode = d.power_mode
                yield result
        yield DeviceSchema(id=OTHER_DEVICE, name="Andere", icon="mdi-home", supported_power_modes=[], power_mode="")


class ReadDevice:
    """Read a device use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read device use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID, home: Home) -> DeviceSchema:
        """Execute the read device use case."""
        async with self.async_session() as session:
            device = await Device.read_by_id(session, device_id)
            if not device:
                raise HTTPException(status_code=404)
            result = DeviceSchema.model_validate(device)
            d = home.get_device(device.id)
            if d is not None:
                result.supported_power_modes = list(d.supported_power_modes)
                result.power_mode = d.power_mode
            return result

class ReadDeviceMeasurements:
    """Read the device measurements use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read device use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID) -> AsyncIterator[DeviceMeasurementSchema]:
        """Execute the read device use case."""
        async with self.async_session() as session:
            async for device_measurement in DeviceMeasurement.read_by_device_id(session, device_id):
                yield DeviceMeasurementSchema.model_validate(device_measurement)

class UpdateDevicePowerMode:
    """Update the power mode of  a device use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a uodate device power mode use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID, power_mode:str, home: Home) -> DeviceSchema:
        """Execute the update device power nmode use case."""
        async with self.async_session.begin() as session:
            d = home.get_device(device_id)
            if d is None:
                raise HTTPException(status_code=404)
            try:
                d.set_power_mode(PowerModes[power_mode.upper()])
                device = await Device.read_by_id(session, device_id)
                if not device:
                    raise HTTPException(status_code=404)

                await device.update(session, device.name, device.icon, power_mode)
                await session.refresh(device)
                result = DeviceSchema.model_validate(device)
                result.supported_power_modes = list(d.supported_power_modes)
                result.power_mode = d.power_mode
                return result
            except Exception:
                logging.error("Invalid power mode: " + power_mode)
                raise HTTPException(status_code=404)

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
