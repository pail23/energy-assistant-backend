"""Tests for utility meters."""


from energy_assistant.devices.utility_meter import UtilityMeter


def test_utility_meter() -> None:
    """Test the utility meter."""
    meter = UtilityMeter("energy")
    assert meter.energy == 0
    meter.update_energy(10)
    assert meter.energy == 10
    meter.update_energy(1)
    assert meter.energy == 10
    meter.update_energy(5)
    assert meter.energy == 14
