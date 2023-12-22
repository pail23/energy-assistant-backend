"""State value supporting the different representation of the states like single value, templates."""

import logging

from jinja2 import Environment, UndefinedError

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices import State, StatesRepository

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)
environment = Environment()


class CalculatedState(State):
    """A numeric, calcuated state."""

    def __init__(self, value: float | str | None) -> None:
        """Create a calculated state instance."""
        if value is None:
            super().__init__("calculated", "0")
        elif isinstance(value, float):
            super().__init__("calculated", str(value))
        else:
            super().__init__("calculated", value)
        self._available = value is not None


class StateValue:
    """State value supporting the different representation of the states like single value, templates."""

    def __init__(self, config: dict | str) -> None:
        """Create a state value instance."""
        self._value_id: str | None = None
        self._template = None
        self._scale: float = 1.0
        if isinstance(config, str):
            self._value_id = config
        else:
            self._value_id = config.get("value")
            self._scale = config.get("scale", 1)
            inverted: bool | None = config.get("inverted")
            if inverted is not None and inverted:
                self._scale = -self._scale
            template: str | None = config.get("template")

            if template is not None:
                self._template = environment.from_string(template)

    def evaluate(self, state_repository: StatesRepository) -> State:
        """Evaluate the value."""
        result: State | None = None
        if self._value_id is not None:
            result = state_repository.get_state(self._value_id)
        else:
            if self._template is not None:
                try:
                    value = self._template.render(state_repository.get_template_states())
                    result = CalculatedState(value)
                except UndefinedError as error:
                    LOGGER.warning(f"undefined variable in expression: {error}")
                    return CalculatedState(None)
        if result is not None:
            return CalculatedState(result.numeric_value * self._scale)
        return CalculatedState(result)

    def set_scale(self, scale: float) -> None:
        """Set the scale for the value. Evaluate multiplies the result with the scale."""
        self._scale = scale

    def invert_value(self) -> None:
        """Set the value to inverted. Evaluate multiples the result with -1."""
        self._scale = -self._scale
