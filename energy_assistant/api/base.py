"""Base utilities for API views to ensure consistency and reduce duplication."""

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from energy_assistant.devices.home import Home
    from energy_assistant.main import EnergyAssistant


def get_energy_assistant(request: Request) -> "EnergyAssistant":
    """Get energy assistant from request with consistent error handling.

    Args:
        request: FastAPI request object

    Returns:
        EnergyAssistant instance

    Raises:
        HTTPException: 500 error if energy assistant is not available

    """
    energy_assistant = getattr(request.app, "energy_assistant", None)
    if energy_assistant is None:
        raise HTTPException(status_code=500, detail="Energy Assistant not available")
    return energy_assistant


def get_home(request: Request) -> "Home":
    """Get home instance from request with consistent error handling.

    Args:
        request: FastAPI request object

    Returns:
        Home instance

    Raises:
        HTTPException: 500 error if home is not available

    """
    home = getattr(request.app, "home", None)
    if home is None:
        energy_assistant = get_energy_assistant(request)
        home = energy_assistant.home
    return home
