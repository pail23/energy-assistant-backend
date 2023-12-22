"""Tests for state value class."""


from energy_assistant.devices import State, StatesSingleRepository
from energy_assistant.devices.state_value import StateValue


class StatesSingleRepositoryMock(StatesSingleRepository):
    """Mock class for a single state repository."""

    def __init__(self, read_states: dict[str, State]) -> None:
        """Create an instance of the StatesSingleRepositoryMock class."""
        super().__init__("test")
        self._read_states = read_states

    def read_states(self) -> None:
        """Read the states from the channel."""
        pass

    def write_states(self) -> None:
        """Write the states to the channel."""
        pass


def test_state_value() -> None:
    """Test the state value."""
    state_repository_read = {
        "sensor.power": State("sensor.power", "10.1"),
        "sensor.energy_low": State("sensor.energy_low", "856"),
        "sensor.energy_high": State("sensor.energy_high", "7"),
    }
    state_repository = StatesSingleRepositoryMock(state_repository_read)
    template_states = state_repository.get_template_states()
    assert "sensor" in template_states
    assert len(template_states["sensor"]) == 3

    state_value = StateValue({"template": "{{sensor.energy_low + sensor.energy_high * 1000}}"})
    assert state_value.evaluate(state_repository).numeric_value == 7856

    state_value = StateValue("sensor.power")
    assert state_value.evaluate(state_repository).numeric_value == 10.1

    state_value = StateValue("sensor.power_unknown")
    assert state_value.evaluate(state_repository).available is False

    state_value = StateValue({"template": "{{sensor.energy_unknown + sensor.energy_high * 1000}}"})
    assert state_value.evaluate(state_repository).available is False

    state_value = StateValue("sensor.power")
    state_value.set_scale(0.001)
    assert state_value.evaluate(state_repository).numeric_value == 0.0101

    state_value = StateValue({"value": "sensor.power"})
    assert state_value.evaluate(state_repository).numeric_value == 10.1

    state_value = StateValue({"value": "sensor.power", "inverted": True})
    assert state_value.evaluate(state_repository).numeric_value == -10.1

    state_value = StateValue(
        {"template": "{{sensor.energy_low + sensor.energy_high * 1000}}", "scale": 0.001}
    )
    assert state_value.evaluate(state_repository).numeric_value == 7.856

    state_value = StateValue({"value": "sensor.power", "scale": 0.001})
    assert state_value.evaluate(state_repository).numeric_value == 0.0101
