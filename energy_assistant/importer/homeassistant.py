"""Homeassistant importer."""

import logging
from datetime import datetime, timedelta
from math import isnan
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices import Location, State, StateId, StatesRepository
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import HistoryState, Homeassistant
from energy_assistant.models.home import HomeMeasurement

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class StatesRepositoryWithHistory(StatesRepository):
    """A state repository for managing historical states."""

    def __init__(self, location: Location) -> None:
        """Create a StatesRepository instance."""
        self._read_states: pd.DataFrame = pd.DataFrame()
        self._template_states: dict[str, dict | Any] | None = None
        self._location = location
        self._selected_date: datetime | None = None

    def set_state_history(self, id: str, history: list[HistoryState], freq: pd.Timedelta) -> None:
        """Set the history of a state."""
        series = pd.Series({x.time_stamp: x.state for x in history})
        series.index = series.index.tz_convert(self._location.get_time_zone())  # type: ignore
        series = series.resample(freq).max().interpolate()
        self._read_states[id] = series

    def select_date(self, d: datetime) -> None:
        """Select the date for the next get_state call."""
        self._selected_date = d

    def get_state(self, id: StateId | str) -> State | None:
        """Get a state from the repository."""
        if self._selected_date is None:
            return None

        _id = id if isinstance(id, str) else id.id

        row = self._read_states.loc[self._selected_date]
        return State(_id, str(row[_id]))

    def get_numeric_states(self) -> dict[str, float]:
        """Get a states from the repository."""
        return {}

    def get_template_states(self) -> dict:
        """Get template states from the repository."""
        if self._template_states is None:
            self._template_states = {}
            states = self.get_numeric_states().items()
            for k, v in states:
                parts = k.split(".")
                if len(parts) > 1:
                    type = parts[0]
                    attribute = parts[1]
                    if type in self._template_states:
                        self._template_states[type][attribute] = v
                    else:
                        self._template_states[type] = {attribute: v}
                else:
                    self._template_states[k] = v
        return self._template_states

    def set_state(self, id: StateId, value: str, attributes: dict | None = None) -> None:
        """Set a state in the repository."""

    @property
    def channel(self) -> str:
        """Get the channel of the State Repository."""
        return "history"

    async def async_read_states(self) -> None:
        """Read the states from the channel asynchronously."""

    def read_states(self) -> None:
        """Read the states from the channel."""

    def write_states(self) -> None:
        """Write the states to the channel."""

    async def async_write_states(self) -> None:
        """Write the states to the channel."""


async def import_data(
    home: Home,
    hass: Homeassistant,
    session: AsyncSession,
    freq: pd.Timedelta,
    days_to_retrieve: int,
) -> None:
    """Import data from Homeassistant."""
    states_repository = StatesRepositoryWithHistory(await hass.get_location())

    start_date = datetime.now(tz=await hass.get_timezone()).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ) - timedelta(days=days_to_retrieve)

    variables = home.get_variables()
    for variable in variables:
        try:
            values = await hass.get_history(variable, start_time=start_date)
            states_repository.set_state_history(variable, values, freq)
        except Exception:
            LOGGER.exception(f"error during fetching the history of state {variable} for Home Assistant")

    # states_repository._read_states.to_csv(Path(settings.DATA_FOLDER)/"state_history.csv")
    energy_state = home.create_home_energy_state_clone()
    for row in states_repository._read_states.iterrows():
        try:
            d: datetime = row[0]  # type: ignore
            states_repository.select_date(d)
            await energy_state.async_update_state(states_repository)
            home_measurement = await HomeMeasurement.read_by_date(session, d.date(), False)
            if home_measurement is None:
                home_measurement = await HomeMeasurement.create(
                    session,
                    name=home.name,
                    measurement_date=d.date(),
                    solar_produced_energy=energy_state.produced_solar_energy,
                    grid_imported_energy=energy_state.grid_imported_energy,
                    grid_exported_energy=energy_state.grid_exported_energy,
                    device_measurements=[],
                )
            elif not isnan(energy_state.grid_exported_energy):
                await home_measurement.update(
                    session,
                    name=home.name,
                    measurement_date=d.date(),
                    solar_produced_energy=energy_state.produced_solar_energy,
                    grid_imported_energy=energy_state.grid_imported_energy,
                    grid_exported_energy=energy_state.grid_exported_energy,
                )
            else:
                LOGGER.error("invalid grid exported value")
        except Exception:
            LOGGER.exception("error during fetching data from the database")
    await session.flush()
    await session.commit()
