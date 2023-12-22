"""Helper classes for data analysis."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
import pathlib
from statistics import mean

import pandas as pd

MAX_DATA_LEN = 3000  # in case of 30 seconds interval, this is about one day.


@dataclass
class DataPoint:
    """Data point for the DataBuffer."""

    value: float
    time_stamp: datetime


class DataBuffer:
    """Data buffer for analysis."""

    def __init__(self) -> None:
        """Create a DataBuffer instance."""
        self.data: deque = deque([], MAX_DATA_LEN)

    def add_data_point(self, value: float, time_stamp: datetime | None = None) -> None:
        """Add a new data point for tracking."""
        if time_stamp is None:
            time_stamp = datetime.now(timezone.utc)
        self.data.append(DataPoint(value, time_stamp))

    def get_data_for(
        self,
        timespan: float,
        now: datetime | None = None,
        without_trailing_zeros: bool = False,
    ) -> list[float]:
        """Extract data for the last timespan seconds."""
        if now is None:
            now = datetime.now(timezone.utc)
        result = []
        threshold = now - timedelta(seconds=timespan)
        for data_point in self.data:
            if data_point.time_stamp >= threshold:
                result.append(data_point.value)
        if without_trailing_zeros:
            while result[-1] == 0.0:
                result.pop()
        return result

    def get_average_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the average over the last timespan seconds."""
        if now is None:
            now = datetime.now(timezone.utc)
        return mean(self.get_data_for(timespan, now))

    def average(self) -> float:
        """Average of the data buffer."""
        if len(self.data) > 0:
            return mean([d.value for d in self.data])
        else:
            return 0.0

    def get_min_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the min over the last timespan seconds."""
        if now is None:
            now = datetime.now(timezone.utc)
        return min(self.get_data_for(timespan, now))

    def get_max_for(self, timespan: float, now: datetime | None = None) -> float:
        """Calculate the max over the last timespan seconds."""
        if now is None:
            now = datetime.now(timezone.utc)
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
            now = datetime.now(timezone.utc)
        data = self.get_data_for(timespan, now, without_trailing_zeros)
        if len(data) > 0:
            if min(data) < lower:
                return False
            return max(data) <= upper
        else:
            return False

    def get_data_frame(
        self,
        freq: pd.Timedelta,
        time_zone: tzinfo,
        value_name: str,
        folder: pathlib.Path,
    ) -> pd.DataFrame:
        """Get a pandas data from from the available data."""
        data = [(pd.to_datetime(d.time_stamp, utc=True), d.value) for d in self.data]
        result = pd.DataFrame.from_records(
            data, index="timestamp", columns=["timestamp", value_name]
        )
        result.to_csv(folder / f"{value_name}.csv")
        result.index = result.index.tz_convert(time_zone)  # type: ignore
        return result.resample(freq).mean()
