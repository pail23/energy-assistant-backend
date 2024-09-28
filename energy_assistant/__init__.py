"""The application."""

import uuid
from abc import ABC, abstractmethod

__version__ = "0.1.13"


class Optimizer(ABC):
    """Base class for optimizers."""

    @abstractmethod
    def get_optimized_power(self, device_id: uuid.UUID) -> float:
        """Get the optimized power budget for a give device."""
