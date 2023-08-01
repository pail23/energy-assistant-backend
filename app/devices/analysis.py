"""Helper classes for data analysis."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean

MAX_DATA_LEN = 3000 # in case of 30 seconds interval, this is about one day.

@dataclass
class DataPoint:
    """Data point for the DataBuffer."""

    value: float
    time_stamp: datetime

class DataBuffer:
    """Data buffer for analysis."""

    def __init__(self) -> None:
        """Create a DataBuffer instance."""
        self.data : deque = deque([], MAX_DATA_LEN)

    def add_data_point(self, value: float, time_stamp: datetime = datetime.now()) -> None:
        """Add a new data point for tracking."""
        self.data.append(DataPoint(value, time_stamp))

    def get_data_for(self, timespan:float, now: datetime = datetime.now()) -> list[float]:
        """Extract data for the last timespan seconds."""
        result = []
        threshold = now - timedelta(seconds=timespan)
        for data_point in self.data:
            if data_point.time_stamp >= threshold:
                result.append(data_point.value)
        return result

    def get_average_for(self, timespan: float, now: datetime = datetime.now()) -> float:
        """Calculate the average over the last timespan seconds."""
        return mean(self.get_data_for(timespan, now))

    def get_min_for(self, timespan: float, now: datetime = datetime.now()) -> float:
        """Calculate the min over the last timespan seconds."""
        return min(self.get_data_for(timespan, now))

    def get_max_for(self, timespan: float, now: datetime = datetime.now()) -> float:
        """Calculate the max over the last timespan seconds."""
        return max(self.get_data_for(timespan, now))
