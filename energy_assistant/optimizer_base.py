"""Base classes and interfaces for optimizers."""

import uuid
from abc import ABC, abstractmethod


class Optimizer(ABC):
    """Base class for optimizers."""

    @abstractmethod
    def get_optimized_power(self, device_id: uuid.UUID) -> float:
        """Get the optimized power budget for a give device."""
