"""Tests for the devices."""
from app.devices import EnergyIntegrator


async def test_integrator() -> None:
    """Test the energy integrator."""
    integrator = EnergyIntegrator()
    integrator.add_measurement(10, 10)
    integrator.add_measurement(10, 10)
    assert integrator.consumed_solar_energy == 11
