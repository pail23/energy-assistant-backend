"""Tests for the base optimizer module."""

import uuid
from abc import ABC

import pytest

from energy_assistant.optimizer.base import Optimizer


class TestOptimizer:
    """Test the base Optimizer class."""

    def test_optimizer_is_abstract(self) -> None:
        """Test that Optimizer is an abstract class."""
        assert issubclass(Optimizer, ABC)

    def test_cannot_instantiate_optimizer_directly(self) -> None:
        """Test that we cannot instantiate Optimizer directly."""
        with pytest.raises(TypeError):
            Optimizer()  # type: ignore

    def test_get_optimized_power_is_abstract(self) -> None:
        """Test that get_optimized_power is an abstract method."""
        assert hasattr(Optimizer, "get_optimized_power")
        assert getattr(Optimizer.get_optimized_power, "__isabstractmethod__", False)


class ConcreteOptimizer(Optimizer):
    """A concrete implementation of Optimizer for testing."""

    def get_optimized_power(self, device_id: uuid.UUID) -> float:
        """Return a fixed power value for testing."""
        return 100.0


class TestConcreteOptimizer:
    """Test a concrete implementation of Optimizer."""

    def test_concrete_optimizer_can_be_instantiated(self) -> None:
        """Test that a concrete optimizer can be instantiated."""
        optimizer = ConcreteOptimizer()
        assert isinstance(optimizer, Optimizer)

    def test_get_optimized_power_returns_float(self) -> None:
        """Test that get_optimized_power returns a float."""
        optimizer = ConcreteOptimizer()
        device_id = uuid.uuid4()
        result = optimizer.get_optimized_power(device_id)
        assert isinstance(result, float)
        assert result == 100.0

    def test_get_optimized_power_with_different_device_ids(self) -> None:
        """Test get_optimized_power with different device IDs."""
        optimizer = ConcreteOptimizer()
        device_id1 = uuid.uuid4()
        device_id2 = uuid.uuid4()
        
        result1 = optimizer.get_optimized_power(device_id1)
        result2 = optimizer.get_optimized_power(device_id2)
        
        assert result1 == 100.0
        assert result2 == 100.0