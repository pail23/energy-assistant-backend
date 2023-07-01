"""Use cases for home measurements."""
from datetime import date
from typing import Union

from fastapi import HTTPException

from app.db import AsyncSession
from app.models.home import HomeMeasurement

from .schema import DeviceMeasurementDifferenceSchema, HomeMeasurementDifferenceSchema


class ReadHomeMeasurementDifference:
    """Read the difference between two home measurementuse case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement use case."""
        self.async_session = session

    async def execute(self, from_date: date, to_date: Union[date, None]) -> HomeMeasurementDifferenceSchema:
        """Execute the read home measurement use case."""
        async with self.async_session() as session:
            home_measurement_from = await HomeMeasurement.read_before_date(session, from_date, include_device_measurements=True)
            if not home_measurement_from:
                home_measurement_from = await HomeMeasurement.read_first(session, include_device_measurements=True)
                if not home_measurement_from:
                    raise HTTPException(status_code=404)
            if to_date is None:
                to_date = date.today()
            home_measurement_to = await HomeMeasurement.read_by_date(session, to_date, include_device_measurements=True)

            if not home_measurement_from:
                raise HTTPException(status_code=404)

            if not home_measurement_to:
                raise HTTPException(status_code=404)

            device_measurements=[]
            for from_device in home_measurement_from.device_measurements:
                to_device = home_measurement_to.get_device_measurement(from_device.device_id) # home_measurement_to.device_measurements[index]
                if to_device is not None:
                    measurement = DeviceMeasurementDifferenceSchema(name = from_device.name, device_id=from_device.device_id,
                        solar_consumed_energy=to_device.solar_consumed_energy - from_device.solar_consumed_energy,
                        consumed_energy=to_device.solar_consumed_energy - from_device.solar_consumed_energy)
                    device_measurements.append(measurement)


            result = HomeMeasurementDifferenceSchema(
                name=home_measurement_from.name,
                consumed_energy=home_measurement_to.consumed_energy - home_measurement_from.consumed_energy,
                solar_consumed_energy=home_measurement_to.solar_consumed_energy - home_measurement_from.solar_consumed_energy,
                solar_produced_energy=home_measurement_to.solar_produced_energy - home_measurement_from.solar_produced_energy,
                grid_exported_energy=home_measurement_to.grid_exported_energy - home_measurement_from.grid_exported_energy,
                grid_imported_energy=home_measurement_to.grid_imported_energy - home_measurement_from.grid_imported_energy,
                device_measurements=device_measurements)

            return result
