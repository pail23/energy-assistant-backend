"""Config storage for Anergy Assistant."""

import logging
import uuid
from pathlib import Path
from typing import Any, Final

import yaml
from anyio import open_file

from ..constants import ROOT_LOGGER_NAME

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)

CONFIG_DATA_FILE: Final = "config_data.yaml"


class ConfigFileError(Exception):
    """Config file errors."""


class DeviceNotFoundError(Exception):
    """The device was not found in the configuration."""


class DeviceConfigMissingParameterError(Exception):
    """Device configuration exception."""

    def __init__(self, missing_param: str) -> None:
        """Create a DeviceConfigError instance."""
        super().__init__(f"Parameter {missing_param} is missing in the configuration")


def merge_dicts(source: dict, destination: dict) -> dict:
    """Merge 2 dictionaries."""
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


def get_dict_value(d: dict, key: str, default_value: Any = None) -> Any:
    """Get the value of a dictionary."""
    parent = d
    subkeys = key.split("/")
    for index, subkey in enumerate(subkeys):
        if index == (len(subkeys) - 1):
            value = parent.get(subkey, default_value)
            if value is None:
                # replace None with default
                return default_value
            return value
        if subkey not in parent:
            # requesting subkey from a non existing parent
            return default_value
        parent = parent[subkey]
    return default_value


def set_dict_value(d: dict, key: str, value: Any) -> None:
    """Set a value in a dictionary."""
    parent = d
    subkeys = key.split("/")
    for index, subkey in enumerate(subkeys):
        if index == (len(subkeys) - 1):
            parent[subkey] = value
        else:
            parent.setdefault(subkey, {})
            parent = parent[subkey]


class ConfigSectionStorageBase:
    """Base class for config file storage."""

    def __init__(self, data_folder: Path, section: str) -> None:
        """Create a ConfigStorage instance."""
        self._data_folder = data_folder
        self._section = section

    @property
    def _config_data_file(self) -> Path:
        return self._data_folder / f"{self._section}_{CONFIG_DATA_FILE}"

    def delete_config_file(self) -> None:
        """Delete the config file on the disk."""
        if self._config_data_file.exists():
            self._config_data_file.unlink()


class ConfigSectionStorage(ConfigSectionStorageBase):
    """Load and store a section from a config file."""

    def __init__(self, data_folder: Path, section: str) -> None:
        """Create a ConfigStorage instance."""
        super().__init__(data_folder, section)
        self._config: dict = {}
        self._data: dict = {}
        self._merged_data: dict = {}

    async def initialize(self, config_file: Path) -> None:
        """Load the config file data."""
        try:
            async with await open_file(config_file) as stream:
                LOGGER.debug("Successfully opened config file %s", config_file)
                config = yaml.safe_load(await stream.read())
                self._config = config.get(self._section, {})
                LOGGER.debug("config file %s successfully loaded", config_file)
        except yaml.YAMLError as error:
            LOGGER.exception("Failed to parse the config file")
            raise ConfigFileError from error
        except FileNotFoundError as error:
            LOGGER.exception("File %s not found", str(config_file))
            raise ConfigFileError from error
        self._data = {}
        if self._config_data_file.exists():
            try:
                async with await open_file(self._config_data_file) as stream:
                    LOGGER.debug("Successfully opened config data file %s", config_file)
                    self._data = yaml.safe_load(await stream.read())
                    LOGGER.debug("config file %s successfully loaded", config_file)
            except yaml.YAMLError as error:
                LOGGER.exception("Failed to parse the config file")
                raise ConfigFileError from error
            except FileNotFoundError:
                self._data = {}
        self._merge_data()

    def _merge_data(self) -> None:
        """Merge the data dictionaries."""
        self._merged_data = merge_dicts(self._data, self._config.copy())

    def store(self) -> None:
        """Store the config data."""
        try:
            #            async with await open_file(self._data_folder/CONFIG_DATA_FILE, mode='w') as stream:
            self._data_folder.mkdir(parents=True, exist_ok=True)
            with self._config_data_file.open(mode="w") as stream:
                yaml.safe_dump(self._data, stream)
        except yaml.YAMLError as error:
            LOGGER.exception("Failed to write the config data file")
            raise ConfigFileError from error

    def set(self, key: str, value: Any) -> None:
        """Set value(s) for a specific key/path in persistent storage."""
        # we support a multi level hierarchy by providing the key as path,
        # with a slash (/) as splitter.
        set_dict_value(self._data, key, value)
        self._merge_data()
        self.store()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value(s) for a specific key/path in persistent storage."""
        return get_dict_value(self._merged_data, key, default)

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get value(s) for a specific key/path in persistent storage."""
        result = get_dict_value(self._merged_data, key, default)
        if result is None:
            raise DeviceConfigMissingParameterError(key)
        return result

    def as_dict(self) -> dict:
        """Get the configuration data as a dictionary."""
        return self._merged_data


class DeviceConfigStorage(ConfigSectionStorageBase):
    """Load and store the device configuration from a config file."""

    def __init__(self, data_folder: Path) -> None:
        """Create a device config storage instance."""
        super().__init__(data_folder, "devices")
        self._config: list[dict] = []
        self._data: list[dict] = []
        self._merged_data: list[dict] = []

    async def initialize(self, config_file: Path) -> None:
        """Load the config file data."""
        try:
            async with await open_file(config_file) as stream:
                LOGGER.debug("Successfully opened config file %s", config_file)
                config = yaml.safe_load(await stream.read())
                self._config = config.get(self._section, [])
                LOGGER.debug("config file %s successfully loaded", config_file)
        except yaml.YAMLError as error:
            LOGGER.exception("Failed to parse the config file")
            raise ConfigFileError from error
        except FileNotFoundError as error:
            LOGGER.exception("File %s not found", str(config_file))
            raise ConfigFileError from error
        self._data = []
        if self._config_data_file.exists():
            try:
                async with await open_file(self._config_data_file) as stream:
                    LOGGER.debug("Successfully opened config data file %s", config_file)
                    self._data = yaml.safe_load(await stream.read())
                    LOGGER.debug("config file %s successfully loaded", config_file)
            except yaml.YAMLError as error:
                LOGGER.exception("Failed to parse the config file")
                raise ConfigFileError from error
            except FileNotFoundError:
                self._data = []
        self._merge_data()

    def _find_device_in_data(self, device_id: str) -> dict:
        for device in self._data:
            if device.get("id") == device_id:
                return device
        return {}

    def _merge_device(self, device: dict) -> dict:
        device_id = device.get("id")
        if device_id is not None:
            data = self._find_device_in_data(device_id)
            return merge_dicts(data, device.copy())
        return {}

    def _merge_data(self) -> None:
        """Merge the data dictionaries."""
        # self._merged_data = merge_dicts(self._data, self._config.copy())
        self._merged_data = [self._merge_device(device) for device in self._config]

    def store(self) -> None:
        """Store the config data."""
        try:
            #            async with await open_file(self._data_folder/CONFIG_DATA_FILE, mode='w') as stream:
            self._data_folder.mkdir(parents=True, exist_ok=True)
            with self._config_data_file.open(mode="w") as stream:
                yaml.safe_dump(self._data, stream)
        except yaml.YAMLError as error:
            LOGGER.exception("Failed to write the config data file")
            raise ConfigFileError from error

    def has_device_config(self, device_id: uuid.UUID) -> bool:
        """Check if a configuration for a device is available."""
        return any(device.get("id") == str(device_id) for device in self._config)

    def get_device_config(self, device_id: uuid.UUID) -> dict:
        """Get the configuration of a device."""
        if self._merged_data is not None:
            for device in self._merged_data:
                if device.get("id") == str(device_id):
                    return device
        raise DeviceNotFoundError

    def get(self, device_id: uuid.UUID, key: str) -> Any:
        """Get a value of a device configuration."""
        device = self.get_device_config(device_id)
        return get_dict_value(device, key)

    def set(self, device_id: uuid.UUID, key: str, value: Any) -> None:
        """Set a config parameter of a device."""
        if not self.has_device_config(device_id):
            raise DeviceNotFoundError

        for device in self._data:
            if device.get("id") == str(device_id):
                set_dict_value(device, key, value)
                self._merge_data()
                self.store()
                return
        device = {"id": str(device_id)}
        set_dict_value(device, key, value)
        self._data.append(device)

        self._merge_data()
        self.store()

    def as_list(self) -> list:
        """Get the configuration data as a list."""
        return self._merged_data


class ConfigStorage:
    """Configuration file storage."""

    def __init__(self, data_folder: Path) -> None:
        """Create an instance of the ConfigurationStorage."""
        self._mqtt = ConfigSectionStorage(data_folder, "mqtt")
        self._homeassistant = ConfigSectionStorage(data_folder, "homeassistant")
        self._home = ConfigSectionStorage(data_folder, "home")
        self._devices = DeviceConfigStorage(data_folder)
        self._emhass = ConfigSectionStorage(data_folder, "emhass")

    async def initialize(self, config_file: Path) -> None:
        """Load the config file data."""
        await self._mqtt.initialize(config_file)
        await self._homeassistant.initialize(config_file)
        await self._home.initialize(config_file)
        await self._devices.initialize(config_file)
        await self._emhass.initialize(config_file)

    @property
    def mqtt(self) -> ConfigSectionStorage:
        """Return the configuration storage for mqtt."""
        return self._mqtt

    @property
    def homeassistant(self) -> ConfigSectionStorage:
        """Return the configuration storage for homeassistant."""
        return self._homeassistant

    @property
    def home(self) -> ConfigSectionStorage:
        """Return the configuration storage for home."""
        return self._home

    @property
    def devices(self) -> DeviceConfigStorage:
        """Return the configuration storage for devices."""
        return self._devices

    @property
    def emhass(self) -> ConfigSectionStorage:
        """Return the configuration storage for emhss."""
        return self._emhass

    def delete_config_file(self) -> None:
        """Delete the config file on the disk."""
        self._mqtt.delete_config_file()
        self._homeassistant.delete_config_file()
        self._home.delete_config_file()
        self._devices.delete_config_file()
        self._emhass.delete_config_file()

    def as_dict(self) -> dict:
        """Get the config data dictionary."""
        return {
            "mqtt": self._mqtt.as_dict(),
            "homeassistant": self._homeassistant.as_dict(),
            "home": self._home.as_dict(),
            "devices": self._devices.as_list(),
            "emhass": self._emhass.as_dict(),
        }
