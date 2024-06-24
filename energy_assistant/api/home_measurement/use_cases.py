"""Use cases for home measurements."""

from collections.abc import AsyncIterator
from datetime import date

from fastapi import HTTPException

from energy_assistant.db import AsyncSession
from energy_assistant.models.home import HomeMeasurement
from energy_assistant.models.schema import HomeMeasurementSchema


class ReadAllHomeMeasurement:
    """Read all home measurements use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read all home measurements use case."""
        self.async_session = session

    async def execute(self) -> AsyncIterator[HomeMeasurementSchema]:
        """Execute the read all home measurements use case."""
        async with self.async_session() as session:
            async for home_measurement in HomeMeasurement.read_all(session, include_device_measurements=True):
                yield HomeMeasurementSchema.model_validate(home_measurement)


class ReadHomeMeasurement:
    """Read a home measurement use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement use case."""
        self.async_session = session

    async def execute(self, home_measurement_id: int) -> HomeMeasurementSchema:
        """Execute the read home measurement use case."""
        async with self.async_session() as session:
            home_measurement = await HomeMeasurement.read_by_id(
                session,
                home_measurement_id,
                include_device_measurements=True,
            )
            if not home_measurement:
                raise HTTPException(status_code=404)
            return HomeMeasurementSchema.model_validate(home_measurement)


class ReadHomeMeasurementByDate:
    """Read a home measurement by date use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement use case."""
        self.async_session = session

    async def execute(self, measurement_date: date) -> HomeMeasurementSchema:
        """Execute the read home measurement use case."""
        async with self.async_session() as session:
            home_measurement = await HomeMeasurement.read_by_date(
                session,
                measurement_date,
                include_device_measurements=True,
            )
            if not home_measurement:
                raise HTTPException(status_code=404)
            return HomeMeasurementSchema.model_validate(home_measurement)


class ReadHomeMeasurementLastBeforeDate:
    """Read the last home measurement before a date use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement use case."""
        self.async_session = session

    async def execute(self, measurement_date: date) -> HomeMeasurementSchema:
        """Execute the read home measurement use case."""
        async with self.async_session() as session:
            home_measurement = await HomeMeasurement.read_before_date(
                session,
                measurement_date,
                include_device_measurements=True,
            )
            if not home_measurement:
                raise HTTPException(status_code=404)
            return HomeMeasurementSchema.model_validate(home_measurement)


class DeleteHomeMeasurement:
    """Delete a home measurement use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a delete a home measurement use case."""
        self.async_session = session

    async def execute(self, home_heasurement_id: int) -> None:
        """Execute the delete a home measurement use case."""
        async with self.async_session.begin() as session:
            home_measurement = await HomeMeasurement.read_by_id(session, home_heasurement_id)
            if not home_measurement:
                return
            await HomeMeasurement.delete(session, home_measurement)
