"""Tests for the data analysis classes."""
from datetime import datetime

import pytest

from app.devices.analysis import DataBuffer


@pytest.fixture
def power_data() -> DataBuffer:
    """Create power data test fixture."""
    result = DataBuffer()
    for x in range(0, 20):
        result.add_data_point( x, datetime(2023, 1, 10, 10, 10, x))
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
