"""State value supporting the different representation of the states like single value, templates."""

import logging
from typing import Any

from jinja2 import Environment, UndefinedError

from app.constants import ROOT_LOGGER_NAME
from app.devices import State, StatesRepository

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


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
        environment = Environment()
        self._value_id: str | None = None
        self._template = None
        self._scale: float = 1.0
        if isinstance(config, str):
            self._value_id = config
        else:
            self._value_id = config.get("value")
            self._scale = config.get("scale", 1)
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
                    value = self._template.render(self.get_template_states(state_repository))
                    result = CalculatedState(value)
                except UndefinedError as error:
                    LOGGER.warn(f"undefined variable in expression: {error}")
                    return CalculatedState(None)
        if result is not None:
            return CalculatedState(result.numeric_value * self._scale)
        return CalculatedState(result)

    def set_scale(self, scale: float) -> None:
        """Set the scale for the value. Evaluate multiplies the result with the scale."""
        self._scale = scale

    def get_template_states(self, state_repository: StatesRepository) -> dict:
        """Get the data structure for the template states."""
        result: dict[str, dict | Any] = {}
        states = state_repository.get_numeric_states().items()
        for k, v in states:
            parts = k.split(".")
            if len(parts) > 1:
                type = parts[0]
                attribute = parts[1]
                if type in result:
                    result[type][attribute] = v
                else:
                    result[type] = {attribute: v}
            else:
                result[k] = v
        return result
