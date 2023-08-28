"""Config helper classes and funtions."""


class DeviceConfigException(Exception):
    """Device configuration exception."""

    pass

def get_config_param(config: dict, param: str) -> str:
    """Get a config paramter as string or raise an exception if the parameter is not available."""
    result = config.get(param)
    if result is None:
        raise DeviceConfigException(f"Parameter {param} is missing in the configuration")
    else:
        return str(result)

def get_config_param_from_list(config: list, param:str) -> str | None:
    """Read config param from a list."""
    for item in config:
        value = item.get(param)
        if value is not None:
            return value
    return None

def get_float_param_from_list(config: list, param:str) -> float | None:
    """Read a float config param from a list."""
    for item in config:
        value = item.get(param)
        if value is not None:
            return float(value)
    return None
