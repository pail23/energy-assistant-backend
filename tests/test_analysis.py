"""Tests for the data analysis classes."""
from datetime import datetime

import pytest

from energy_assistant.devices.analysis import DataBuffer


@pytest.fixture
def power_data() -> DataBuffer:
    """Create power data test fixture."""
    result = DataBuffer()
    for x in range(0, 20):
        result.add_data_point(x, datetime(2023, 1, 10, 10, 10, x))
    return result


@pytest.fixture
def power_data_with_trailing_zeros() -> DataBuffer:
    """Create power data test fixture."""
    result = DataBuffer()
    for x in range(0, 20):
        result.add_data_point(x, datetime(2023, 1, 10, 10, 10, x))
    for y in range(0, 3):
        result.add_data_point(0.0, datetime(2023, 1, 10, 10, 10, 20 + y))
    return result


def test_min(power_data: DataBuffer):
    """Test the data buffer minimum calculation."""
    min = power_data.get_min_for(5, datetime(2023, 1, 10, 10, 10, 21))
    assert min == 16


def test_max(power_data: DataBuffer):
    """Test the data buffer maximum calculation."""
    max = power_data.get_max_for(5, datetime(2023, 1, 10, 10, 10, 21))
    assert max == 19


def test_average(power_data: DataBuffer):
    """Test the data buffer average calculation."""
    avg = power_data.get_average_for(5, datetime(2023, 1, 10, 10, 10, 21))
    assert avg == 17.5


def test_get_data_without_trailing_zeros(power_data_with_trailing_zeros: DataBuffer):
    """Test getting the data without the trailing zeros."""
    data = power_data_with_trailing_zeros.get_data_for(8, datetime(2023, 1, 10, 10, 10, 23), True)
    assert len(data) == 5
    assert data == [15, 16, 17, 18, 19]


def test_is_between_without_trailing_zeros(power_data_with_trailing_zeros: DataBuffer):
    """Test getting the data without the trailing zeros."""
    data = power_data_with_trailing_zeros.is_between(
        15, 19, 8, datetime(2023, 1, 10, 10, 10, 23), True
    )
    assert data
