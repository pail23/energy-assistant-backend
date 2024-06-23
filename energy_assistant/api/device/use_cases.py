"""Use cases for devices."""

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import HTTPException

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.db import AsyncSession
from energy_assistant.devices import PowerModes
from energy_assistant.devices.home import Home
from energy_assistant.models.device import Device, DeviceMeasurement
from energy_assistant.models.schema import DeviceMeasurementSchema, DeviceSchema

from . import OTHER_DEVICE

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class ReadAllDevices:
    """Read all devices use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read all devices use case."""
        self.async_session = session

    async def execute(self, home: Home | None, filter_with_session_log_enties: bool) -> AsyncIterator[DeviceSchema]:
        """Execute the read all devices use case."""
        async with self.async_session() as session:
            async for device in Device.read_all(session, False, filter_with_session_log_enties):
                if device.type is not None and (
                    not filter_with_session_log_enties or len(device.session_log_entries) > 0
                ):
                    result = DeviceSchema.model_validate(device)
                    d = home.get_device(device.id) if home is not None else None
                    if d is not None:
                        result.supported_power_modes = list(d.supported_power_modes)
                        result.power_mode = d.power_mode
                    yield result
        if not filter_with_session_log_enties:
            yield DeviceSchema(
                id=OTHER_DEVICE,
                name="Other",
                icon="mdi-home",
                type="other",
                config="",
                supported_power_modes=[],
                power_mode="",
            )


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

    async def execute(self, device_id: uuid.UUID, power_mode: str, home: Home) -> DeviceSchema:
        """Execute the update device power nmode use case."""
        async with self.async_session.begin() as session:
            d = home.get_device(device_id)
            if d is None:
                raise HTTPException(status_code=404)
            try:
                d.set_power_mode(PowerModes[power_mode.upper()])
                device = await Device.read_by_id(session, device_id)
            except Exception as err:
                LOGGER.exception("Invalid power mode %s ", power_mode)
                raise HTTPException(status_code=404) from err

            if not device:
                raise HTTPException(status_code=404)

            if device.type is None:
                raise HTTPException(status_code=500)

            try:
                await device.update(session, device.name, device.icon, power_mode, device.type, device.get_config())
                await session.refresh(device)
                result = DeviceSchema.model_validate(device)
                result.supported_power_modes = list(d.supported_power_modes)
                result.power_mode = d.power_mode
            except Exception as err:
                LOGGER.exception("Invalid power mode %s ", power_mode)
                raise HTTPException(status_code=404) from err
            else:
                return result


class DeleteDevice:
    """Delete a device use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a delete a device use case."""
        self.async_session = session

    async def execute(self, device_id: uuid.UUID, home: Home | None) -> None:
        """Execute the delete a device use case."""
        async with self.async_session.begin() as session:
            device = await Device.read_by_id(session, device_id)
            if not device:
                return
            await Device.delete(session, device)
            if home is not None:
                home.remove_device(device_id)
