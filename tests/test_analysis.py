"""Tests for the data analysis classes."""

from datetime import UTC, datetime
from math import floor
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from energy_assistant.devices.analysis import DataBuffer, FloatDataBuffer, OnOffDataBuffer, create_timeseries_from_const

time_zone = ZoneInfo("Europe/Berlin")


@pytest.fixture()
def power_data() -> FloatDataBuffer:
    """Create power data test fixture."""
    result = FloatDataBuffer()
    for x in range(20):
        result.add_data_point(x, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    return result


@pytest.fixture()
def power_data_with_trailing_zeros() -> FloatDataBuffer:
    """Create power data test fixture."""
    result = FloatDataBuffer()
    for x in range(20):
        result.add_data_point(x, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    for y in range(3):
        result.add_data_point(0.0, datetime(2023, 1, 10, 10, 10, 20 + y, tzinfo=time_zone))
    return result


def test_add_data_point_if_different(power_data: FloatDataBuffer) -> None:
    """Test adding a data point only if it's different from the last one."""
    assert len(power_data.data) == 20
    power_data.add_data_point_if_different(19, datetime(2023, 1, 10, 10, 10, 21, tzinfo=time_zone))
    assert len(power_data.data) == 20
    assert power_data.data[-1].value == 19


def test_min(power_data: FloatDataBuffer) -> None:
    """Test the data buffer minimum calculation."""
    min = power_data.get_min_for(5, datetime(2023, 1, 10, 10, 10, 21, tzinfo=time_zone))
    assert min == 16


def test_max(power_data: FloatDataBuffer) -> None:
    """Test the data buffer maximum calculation."""
    max = power_data.get_max_for(5, datetime(2023, 1, 10, 10, 10, 21, tzinfo=time_zone))
    assert max == 19


def test_average(power_data: FloatDataBuffer) -> None:
    """Test the data buffer average calculation."""
    avg = power_data.get_average_for(5, datetime(2023, 1, 10, 10, 10, 21, tzinfo=time_zone))
    assert avg == 17.5


def test_get_data_without_trailing_zeros(power_data_with_trailing_zeros: FloatDataBuffer) -> None:
    """Test getting the data without the trailing zeros."""
    data = power_data_with_trailing_zeros.get_data_for(8, datetime(2023, 1, 10, 10, 10, 23, tzinfo=time_zone), True)
    assert len(data) == 5
    assert data == [15, 16, 17, 18, 19]


def test_is_between_without_trailing_zeros(power_data_with_trailing_zeros: FloatDataBuffer) -> None:
    """Test getting the data without the trailing zeros."""
    data = power_data_with_trailing_zeros.is_between(
        15,
        19,
        8,
        datetime(2023, 1, 10, 10, 10, 23, tzinfo=time_zone),
        True,
    )
    assert data


def test_create_timeseries_from_const() -> None:
    """Test creation of a constant time series."""
    data = create_timeseries_from_const(
        15,
        pd.Timedelta(60, "m"),
        pd.Timedelta(30, "s"),
        pd.Timestamp(2024, 1, 1, 12, 30, 15),
    )
    assert data.size == 121
    assert not data.hasnans
    assert data.min() == 15
    assert data.max() == 15


def test_on_off_data_buffer() -> None:
    """Test initialization of the on /off data buffer."""
    start = datetime.now(UTC)
    data = OnOffDataBuffer()
    for x in range(4000):
        data.add_data_point(False, datetime(2023, 1, 10, floor(x / 3600), floor(x / 60) % 60, x % 60, tzinfo=time_zone))
    assert len(data.data) == 3000
    delta = datetime.now(UTC) - start
    print(f"duration is {delta}")


def test_duration_in_state() -> None:
    """Test calculating the duration in a given state."""
    data_buffer = OnOffDataBuffer()

    now = datetime(2023, 1, 10, 10, 10, 20, tzinfo=time_zone)
    for x in range(12):
        data_buffer.add_data_point(x % 4 == 0, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    duration = data_buffer.duration_in_state(True, now)
    assert duration.total_seconds() == 0

    duration = data_buffer.duration_in_state(False, now)
    assert duration.total_seconds() == 11

    # Test with no data points in the state
    duration = data_buffer.duration_in_state(True, datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone))
    assert duration.total_seconds() == 0

    duration = data_buffer.duration_in_state(False, datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone))
    assert duration.total_seconds() == 0

    # Test with no data points at all
    empty_buffer = OnOffDataBuffer()
    duration = empty_buffer.duration_in_state(True, now)
    assert duration.total_seconds() == 0

    duration = empty_buffer.duration_in_state(False, now)
    assert duration.total_seconds() == 0

    # Test with a single data point
    single_point_buffer = OnOffDataBuffer()
    single_point_buffer.add_data_point(True, datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone))
    duration = single_point_buffer.duration_in_state(True, now)
    assert duration.total_seconds() == (now - datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone)).total_seconds()

    duration = single_point_buffer.duration_in_state(False, now)
    assert duration.total_seconds() == 0

    # Test with a single data point in the False state
    single_point_buffer = OnOffDataBuffer()
    single_point_buffer.add_data_point(False, datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone))
    duration = single_point_buffer.duration_in_state(False, now)
    assert duration.total_seconds() == (now - datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone)).total_seconds()

    duration = single_point_buffer.duration_in_state(True, now)
    assert duration.total_seconds() == 0


def test_total_duration_in_state_since() -> None:
    """Test calculating the total duration in a given state since a specific time."""
    data_buffer = OnOffDataBuffer()

    now = datetime(2023, 1, 10, 10, 10, 20, tzinfo=time_zone)
    since = datetime(2023, 1, 10, 10, 10, 5, tzinfo=time_zone)
    for x in range(12):
        data_buffer.add_data_point(x % 4 == 0, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))

    duration = data_buffer.total_duration_in_state_since(True, since, now)
    assert duration.total_seconds() == 1

    duration = data_buffer.total_duration_in_state_since(False, since, now)
    assert duration.total_seconds() == 14


def test_total_duration_in_state_since_with_one_data_point() -> None:
    """Test calculating the total duration in a given state since a specific time."""
    data_buffer = OnOffDataBuffer()

    now = datetime(2023, 1, 10, 10, 10, 20, tzinfo=time_zone)
    since = datetime(2023, 1, 10, 10, 10, 5, tzinfo=time_zone)
    data_buffer.add_data_point(True, datetime(2023, 1, 10, 10, 10, 10, tzinfo=time_zone))

    duration = data_buffer.total_duration_in_state_since(True, since, now)
    assert duration.total_seconds() == 10

    duration = data_buffer.total_duration_in_state_since(False, since, now)
    assert duration.total_seconds() == 0


@pytest.fixture()
def data_buffer() -> DataBuffer[int]:
    """Create a DataBuffer test fixture."""
    return DataBuffer[int]()


def test_add_data_point(data_buffer: DataBuffer[int]) -> None:
    """Test adding a data point to the data buffer."""
    time_stamp = datetime(2023, 1, 10, 10, 10, 0, tzinfo=time_zone)
    data_buffer.add_data_point(10, time_stamp)
    assert len(data_buffer.data) == 1
    assert data_buffer.data[0].value == 10
    assert data_buffer.data[0].time_stamp == time_stamp


def test_add_data_point_without_timestamp(data_buffer: DataBuffer[int]) -> None:
    """Test adding a data point without a timestamp."""
    data_buffer.add_data_point(20)
    assert len(data_buffer.data) == 1
    assert data_buffer.data[0].value == 20
    assert data_buffer.data[0].time_stamp <= datetime.now(UTC)


def test_get_data_for(data_buffer: DataBuffer[int]) -> None:
    """Test extracting data for the last timespan seconds."""
    now = datetime(2023, 1, 10, 10, 10, 10, tzinfo=time_zone)
    for x in range(10):
        data_buffer.add_data_point(x, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    result = data_buffer.get_data_for(5, now)
    assert result == [5, 6, 7, 8, 9]


def test_get_data_for_without_trailing_zeros(data_buffer: DataBuffer[int]) -> None:
    """Test extracting data for the last timespan seconds without trailing zeros."""
    now = datetime(2023, 1, 10, 10, 10, 20, tzinfo=time_zone)
    for x in range(10):
        data_buffer.add_data_point(x, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    for y in range(7):
        data_buffer.add_data_point(0, datetime(2023, 1, 10, 10, 10, 10 + y, tzinfo=time_zone))
    result = data_buffer.get_data_for(15, now, True)
    assert result == [5, 6, 7, 8, 9]


def test_get_data_frame(data_buffer: DataBuffer[int]) -> None:
    """Test getting a pandas data frame from the available data."""
    for x in range(10):
        data_buffer.add_data_point(x, datetime(2023, 1, 10, 10, 10, x, tzinfo=time_zone))
    freq = pd.Timedelta(seconds=1)
    result = data_buffer.get_data_frame(freq, time_zone, "value")
    assert not result.empty
    assert result.index.tzinfo == time_zone
    assert result["value"].iloc[0] == 0
    assert result["value"].iloc[-1] == 9
