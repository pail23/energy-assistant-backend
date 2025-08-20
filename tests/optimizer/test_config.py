"""Tests for the config module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock external dependencies before importing the modules
mock_emhass = MagicMock()
mock_emhass.utils = MagicMock()
mock_emhass.utils.get_yaml_parse = MagicMock(return_value=(
    {"test_retrieve": "config"},
    {"test_optim": "config"},
    {"test_plant": "config"}
))
sys.modules['emhass'] = mock_emhass
sys.modules['emhass.utils'] = mock_emhass.utils

from energy_assistant.devices import Location
from energy_assistant.devices.homeassistant import Homeassistant
from energy_assistant.optimizer.config import DEFAULT_COST_FUNC, DEFAULT_HASS_ENTITY_PREFIX, EmhassConfig
from energy_assistant.storage.config import ConfigStorage


@pytest.fixture
def mock_location() -> Location:
    """Create a mock location for testing."""
    location = MagicMock(spec=Location)
    location.latitude = 52.5
    location.longitude = 13.4
    location.elevation = 50
    location.get_time_zone.return_value = "Europe/Berlin"
    return location


@pytest.fixture
def mock_hass() -> Homeassistant:
    """Create a mock Home Assistant for testing."""
    hass = MagicMock(spec=Homeassistant)
    hass.url = "http://localhost:8123"
    hass.token = "test_token"
    return hass


@pytest.fixture
def mock_config_storage() -> ConfigStorage:
    """Create a mock config storage for testing."""
    config = MagicMock(spec=ConfigStorage)
    config.home = {"solar_power": "sensor.solar_power"}
    config.emhass = MagicMock()
    config.emhass.as_dict.return_value = {
        "plant_conf": {},
        "retrieve_hass_conf": {
            "optimization_time_step": 3600
        },
        "optim_conf": {},
    }
    return config


@pytest.fixture
def empty_config_storage() -> ConfigStorage:
    """Create an empty config storage for testing."""
    config = MagicMock(spec=ConfigStorage)
    config.home = None
    config.emhass = MagicMock()
    config.emhass.as_dict.return_value = None
    return config


class TestEmhassConfig:
    """Test the EmhassConfig class."""

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_init_with_config(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test EmhassConfig initialization with configuration."""
        data_folder = "/test/data"

        emhass_config = EmhassConfig(data_folder, mock_config_storage, mock_hass, mock_location)

        assert emhass_config.solar_power_id == "sensor.solar_power"
        assert emhass_config.hass_entity_prefix == DEFAULT_HASS_ENTITY_PREFIX
        assert emhass_config.pv_forecast_method == "homeassistant"
        assert emhass_config.cost_fun == "profit"
        assert emhass_config.method_ts_round == "nearest"
        mock_mkdir.assert_called()

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_init_without_config(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        empty_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test EmhassConfig initialization without configuration."""
        data_folder = "/test/data"

        emhass_config = EmhassConfig(data_folder, empty_config_storage, mock_hass, mock_location)

        assert emhass_config.solar_power_id is None
        assert emhass_config.pv_forecast_method == "homeassistant"
        assert emhass_config.cost_fun == DEFAULT_COST_FUNC
        assert emhass_config.hass_entity_prefix == DEFAULT_HASS_ENTITY_PREFIX
        mock_mkdir.assert_called()

    def test_hass_url_normalization(
        self,
        mock_config_storage: ConfigStorage,
        mock_location: Location,
    ) -> None:
        """Test that HASS URL is normalized with trailing slash."""
        hass = MagicMock(spec=Homeassistant)
        hass.url = "http://localhost:8123"  # No trailing slash
        hass.token = "test_token"

        with patch("energy_assistant.optimizer.config.pathlib.Path.mkdir"), \
             patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False):
            emhass_config = EmhassConfig("/test/data", mock_config_storage, hass, mock_location)

            # Check that URL is normalized in internal state
            assert emhass_config._hass_url == "http://localhost:8123/"

    def test_hass_url_no_double_slash(
        self,
        mock_config_storage: ConfigStorage,
        mock_location: Location,
    ) -> None:
        """Test that HASS URL doesn't get double slash if already present."""
        hass = MagicMock(spec=Homeassistant)
        hass.url = "http://localhost:8123/"  # Already has trailing slash
        hass.token = "test_token"

        with patch("energy_assistant.optimizer.config.pathlib.Path.mkdir"), \
             patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False):
            emhass_config = EmhassConfig("/test/data", mock_config_storage, hass, mock_location)

            # Should not add another slash
            assert emhass_config._hass_url == "http://localhost:8123/"

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_power_no_var_loads_id_generation(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test generation of power no var loads ID."""
        emhass_config = EmhassConfig("/test/data", mock_config_storage, mock_hass, mock_location)

        # Should generate a default ID
        assert emhass_config.power_no_var_loads_id.startswith("sensor.em_power_load_no_var_loads")

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_retrieve_hass_conf_setup(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test that retrieve_hass_conf is properly set up."""
        emhass_config = EmhassConfig("/test/data", mock_config_storage, mock_hass, mock_location)

        assert emhass_config.retrieve_hass_conf["hass_url"] == "http://localhost:8123/"
        assert emhass_config.retrieve_hass_conf["long_lived_token"] == "test_token"
        assert emhass_config.retrieve_hass_conf["sensor_power_photovoltaics"] == "sensor.solar_power"
        assert emhass_config.retrieve_hass_conf["time_zone"] == "Europe/Berlin"
        assert emhass_config.retrieve_hass_conf["Latitude"] == 52.5
        assert emhass_config.retrieve_hass_conf["Longitude"] == 13.4
        assert emhass_config.retrieve_hass_conf["alt"] == 50
        assert emhass_config.retrieve_hass_conf["continual_publish"] is False

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_optim_conf_setup(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test that optim_conf is properly set up."""
        emhass_config = EmhassConfig("/test/data", mock_config_storage, mock_hass, mock_location)

        assert emhass_config.optim_conf["number_of_deferrable_loads"] == 0

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_plant_conf_setup(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test that plant_conf is properly set up."""
        emhass_config = EmhassConfig("/test/data", mock_config_storage, mock_hass, mock_location)

        assert emhass_config.plant_conf["compute_curtailment"] is False

    @patch("energy_assistant.optimizer.config.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.config.pathlib.Path.exists", return_value=False)
    def test_properties_access(
        self,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test that all properties can be accessed."""
        emhass_config = EmhassConfig("/test/data", mock_config_storage, mock_hass, mock_location)

        assert isinstance(emhass_config.solar_power_id, str)
        assert isinstance(emhass_config.power_no_var_loads_id, str)
        assert isinstance(emhass_config.hass_entity_prefix, str)
        assert isinstance(emhass_config.pv_forecast_method, str)
        assert isinstance(emhass_config.cost_fun, str)
        assert isinstance(emhass_config.method_ts_round, str)
        assert isinstance(emhass_config.retrieve_hass_conf, dict)
        assert isinstance(emhass_config.optim_conf, dict)
        assert isinstance(emhass_config.plant_conf, dict)
        assert emhass_config.emhass_config is not None
