"""Helper classes for data analysis."""

import pathlib
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from statistics import mean
from typing import Generic, TypeVar

import pandas as pd

MAX_DATA_LEN = 3000  # in case of 30 seconds interval, this is about one day.


T = TypeVar("T")


@dataclass
class DataPoint(Generic[T]):
    """Data point for the DataBuffer."""

    value: T
    time_stamp: datetime


class DataBuffer(Generic[T]):
    """Data buffer for analysis."""

    def __init__(self) -> None:
        """Create a DataBuffer instance."""
        self.data: deque = deque([], MAX_DATA_LEN)

    def add_data_point(self, value: T, time_stamp: datetime | None = None) -> None:
        """Add a new data point for tracking."""
        if time_stamp is None:
            time_stamp = datetime.now(UTC)
        self.data.append(DataPoint[T](value, time_stamp))

    def get_data_for(
        self,
        timespan: float,
        now: datetime | None = None,
        without_trailing_zeros: bool = False,
    ) -> list[T]:
        """Extract data for the last timespan seconds."""
        if now is None:
            now = datetime.now(UTC)
        threshold = now - timedelta(seconds=timespan)
        result = [data_point.value for data_point in self.data if data_point.time_stamp >= threshold]
        if len(result) == 0:
            result = [self.data[-1].value]
        if without_trailing_zeros:
            while result[-1] == 0.0:
                result.pop()
        return result

    def get_data_frame(
        self,
        freq: pd.Timedelta,
        time_zone: tzinfo,
        value_name: str,
        folder: pathlib.Path | None = None,
    ) -> pd.DataFrame:
        """Get a pandas data frame from from the available data."""
        data = [(pd.to_datetime(d.time_stamp, utc=True), d.value) for d in self.data]
        result = pd.DataFrame.from_records(data, index="timestamp", columns=["timestamp", value_name])
        if folder is not None:
            result.to_csv(folder / f"{value_name}.csv")
        if not result.empty:
            result.index = result.index.tz_convert(time_zone)  # type: ignore
            return result.resample(freq).mean()
        return result


class OnOffDataBuffer(DataBuffer[bool]):
    """Data buffer for OnOff States."""

    pass


class FloatDataBuffer(DataBuffer[float]):
    """Data buffer for float values."""

    def get_average_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the average over the last timespan seconds."""
        if now is None:
            now = datetime.now(UTC)
        return mean(self.get_data_for(timespan, now))

    def average(self) -> float:
        """Average of the data buffer."""
        if len(self.data) > 0:
            return mean([d.value for d in self.data])
        return 0.0

    def get_min_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the min over the last timespan seconds."""
        if now is None:
            now = datetime.now(UTC)
        return min(self.get_data_for(timespan, now))

    def get_max_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the max over the last timespan seconds."""
        if now is None:
            now = datetime.now(UTC)
        return max(self.get_data_for(timespan, now))

    def is_between(
        self,
        lower: float,
        upper: float,
        timespan: float,
        now: datetime | None = None,
        without_trailing_zeros: bool = False,
    ) -> bool:
        """Check if the value in the timespan is always between lower and upper."""
        if now is None:
            now = datetime.now(UTC)
        data = self.get_data_for(timespan, now, without_trailing_zeros)
        if len(data) > 0:
            if min(data) < lower:
                return False
            return max(data) <= upper
        return False


def create_timeseries_from_const(
    value: float,
    duration: pd.Timedelta,
    freq: pd.Timedelta,
    start: pd.Timestamp | None = None,
) -> pd.Series:
    """Create a time series with constant values."""
    if start is None:
        start = pd.Timestamp.utcnow()
    data = [value, value]
    index = [start, start + duration]
    result = pd.Series(data=data, index=index)
    return result.resample(freq).bfill()
