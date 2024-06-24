"""Use cases for home measurements."""

from datetime import date

from fastapi import HTTPException

from energy_assistant.api.device import OTHER_DEVICE
from energy_assistant.db import AsyncSession
from energy_assistant.models.home import (
    HomeMeasurement,
    get_consumed_energy,
    get_consumed_solar_energy,
)

from .schema import (
    DeviceMeasurementPeriodSchema,
    HomeMeasurementDailySchema,
    HomeMeasurementDateSchema,
    HomeMeasurementPeriodSchema,
)


def add_others_device(
    home_measurement: HomeMeasurementPeriodSchema,
) -> HomeMeasurementPeriodSchema:
    """Add the date for the others device."""
    solar_consumed_energy = home_measurement.solar_consumed_energy
    consumed_energy = home_measurement.consumed_energy
    for device_measurement in home_measurement.device_measurements:
        solar_consumed_energy = solar_consumed_energy - device_measurement.solar_consumed_energy
        consumed_energy = consumed_energy - device_measurement.consumed_energy
    other_device = DeviceMeasurementPeriodSchema(
        solar_consumed_energy=solar_consumed_energy,
        consumed_energy=consumed_energy,
        device_id=OTHER_DEVICE,
    )
    home_measurement.device_measurements.append(other_device)
    return home_measurement


class ReadHomeMeasurementDifference:
    """Read the difference between two home measurementuse case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement use case."""
        self.async_session = session

    async def execute(self, from_date: date, to_date: date) -> HomeMeasurementPeriodSchema:
        """Execute the read home measurement use case."""
        async with self.async_session() as session:
            home_measurement_from = await HomeMeasurement.read_before_date(
                session,
                from_date,
                include_device_measurements=True,
            )
            if not home_measurement_from:
                home_measurement_from = await HomeMeasurement.read_first(session, include_device_measurements=True)
                if not home_measurement_from:
                    raise HTTPException(status_code=404)
            home_measurement_to = await HomeMeasurement.read_by_date(session, to_date, include_device_measurements=True)

            if not home_measurement_from:
                raise HTTPException(status_code=404)

            if not home_measurement_to:
                raise HTTPException(status_code=404)

            device_measurements = []
            for from_device in home_measurement_from.device_measurements:
                to_device = home_measurement_to.get_device_measurement(
                    from_device.device_id,
                )  # home_measurement_to.device_measurements[index]
                if to_device is not None:
                    measurement = DeviceMeasurementPeriodSchema(
                        device_id=from_device.device_id,
                        solar_consumed_energy=to_device.solar_consumed_energy - from_device.solar_consumed_energy,
                        consumed_energy=to_device.consumed_energy - from_device.consumed_energy,
                    )
                    device_measurements.append(measurement)

            result = HomeMeasurementPeriodSchema(
                consumed_energy=get_consumed_energy(home_measurement_to) - get_consumed_energy(home_measurement_from),
                solar_consumed_energy=get_consumed_solar_energy(home_measurement_to)
                - get_consumed_solar_energy(home_measurement_from),
                solar_produced_energy=home_measurement_to.solar_produced_energy
                - home_measurement_from.solar_produced_energy,
                grid_exported_energy=home_measurement_to.grid_exported_energy
                - home_measurement_from.grid_exported_energy,
                grid_imported_energy=home_measurement_to.grid_imported_energy
                - home_measurement_from.grid_imported_energy,
                device_measurements=device_measurements,
            )

            return add_others_device(result)


class ReadHomeMeasurementDaily:
    """Read the daily usage between two dates use case."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a read home measurement dates use case."""
        self.async_session = session

    async def execute(self, from_date: date, to_date: date) -> HomeMeasurementDailySchema:
        """Execute the read daily home measurement use case."""
        async with self.async_session() as session:
            last_measurement = await HomeMeasurement.read_before_date(
                session,
                from_date,
                include_device_measurements=True,
            )
            if not last_measurement:
                last_measurement = await HomeMeasurement.read_first(session, include_device_measurements=True)
                if not last_measurement:
                    raise HTTPException(status_code=404)
            result = []
            async for home_measurement in HomeMeasurement.read_between_dates(session, from_date, to_date, True):
                device_measurements = []
                for from_device in last_measurement.device_measurements:
                    to_device = home_measurement.get_device_measurement(from_device.device_id)
                    if to_device is not None:
                        device_measurement = DeviceMeasurementPeriodSchema(
                            device_id=from_device.device_id,
                            solar_consumed_energy=to_device.solar_consumed_energy - from_device.solar_consumed_energy,
                            consumed_energy=to_device.consumed_energy - from_device.consumed_energy,
                        )
                        device_measurements.append(device_measurement)
                measurement = HomeMeasurementDateSchema(
                    solar_consumed_energy=get_consumed_solar_energy(home_measurement)
                    - get_consumed_solar_energy(last_measurement),
                    consumed_energy=get_consumed_energy(home_measurement) - get_consumed_energy(last_measurement),
                    solar_produced_energy=home_measurement.solar_produced_energy
                    - last_measurement.solar_produced_energy,
                    grid_imported_energy=home_measurement.grid_imported_energy - last_measurement.grid_imported_energy,
                    grid_exported_energy=home_measurement.grid_exported_energy - last_measurement.grid_exported_energy,
                    measurement_date=home_measurement.measurement_date,
                    device_measurements=device_measurements,
                )
                add_others_device(measurement)
                result.append(measurement)
                last_measurement = home_measurement
            return HomeMeasurementDailySchema(measurements=result)
