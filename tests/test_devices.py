"""Tests for the devices."""
from app.devices import EnergyIntegrator


def test_integrator() -> None:
    """Test the energy integrator."""
    integrator = EnergyIntegrator()
    integrator.add_measurement(10, 0)
    integrator.add_measurement(20, 0.1)
    assert integrator.consumed_solar_energy == 11
