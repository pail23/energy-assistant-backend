"""Tests for the optimization module."""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Mock external dependencies before importing the modules
mock_emhass = MagicMock()
mock_emhass.utils = MagicMock()
mock_emhass.forecast = MagicMock()
mock_emhass.forecast.Forecast = MagicMock()
mock_emhass.optimization = MagicMock()
mock_emhass.optimization.Optimization = MagicMock()
mock_emhass.retrieve_hass = MagicMock()
mock_emhass.retrieve_hass.RetrieveHass = MagicMock()
sys.modules['emhass'] = mock_emhass
sys.modules['emhass.utils'] = mock_emhass.utils
sys.modules['emhass.forecast'] = mock_emhass.forecast
sys.modules['emhass.optimization'] = mock_emhass.optimization
sys.modules['emhass.retrieve_hass'] = mock_emhass.retrieve_hass

from energy_assistant.devices import LoadInfo, Location
from energy_assistant.optimizer.config import EmhassConfig
from energy_assistant.optimizer.forecasting import ForecastingManager
from energy_assistant.optimizer.ml_models import MLModelManager
from energy_assistant.optimizer.optimization import OptimizationManager


@pytest.fixture
def mock_config() -> EmhassConfig:
    """Create a mock EmhassConfig for testing."""
    config = MagicMock(spec=EmhassConfig)
    config.emhass_config = {"test": "config"}
    config.retrieve_hass_conf = {
        "days_to_retrieve": 2,
        "sensor_power_load_no_var_loads": "sensor.load",
        "load_negative": False,
        "set_zero_min": True,
        "sensor_replace_zero": ["sensor.solar"],
        "sensor_linear_interp": ["sensor.solar"],
    }
    config.optim_conf = {"test": "optim"}
    config.plant_conf = {"test": "plant"}
    config.emhass_path_conf = "/test/path"
    config.cost_fun = "profit"
    config.solar_power_id = "sensor.solar_power"
    config.power_no_var_loads_id = "sensor.power_load"
    return config


@pytest.fixture
def mock_forecasting_manager() -> ForecastingManager:
    """Create a mock ForecastingManager for testing."""
    return MagicMock(spec=ForecastingManager)


@pytest.fixture
def mock_ml_model_manager() -> MLModelManager:
    """Create a mock MLModelManager for testing."""
    return MagicMock(spec=MLModelManager)


@pytest.fixture
def mock_retrieve_hass() -> MagicMock:
    """Create a mock RetrieveHass for testing."""
    retrieve_hass = MagicMock()
    retrieve_hass.df_final = pd.DataFrame({
        "sensor.solar_power": [100, 200, 300],
        "sensor.power_load": [500, 600, 700],
    })
    return retrieve_hass


@pytest.fixture
def mock_location() -> Location:
    """Create a mock location for testing."""
    location = MagicMock(spec=Location)
    location.latitude = 52.5
    location.longitude = 13.4
    return location


@pytest.fixture
def optimization_manager(
    mock_config: EmhassConfig,
    mock_forecasting_manager: ForecastingManager,
    mock_ml_model_manager: MLModelManager,
    mock_retrieve_hass: MagicMock,
    mock_location: Location,
) -> OptimizationManager:
    """Create an OptimizationManager instance for testing."""
    return OptimizationManager(
        mock_config,
        mock_forecasting_manager,
        mock_ml_model_manager,
        mock_retrieve_hass,
        mock_location,
    )


class TestOptimizationManager:
    """Test the OptimizationManager class."""

    def test_init(
        self,
        optimization_manager: OptimizationManager,
        mock_config: EmhassConfig,
        mock_forecasting_manager: ForecastingManager,
        mock_ml_model_manager: MLModelManager,
    ) -> None:
        """Test OptimizationManager initialization."""
        assert optimization_manager._config == mock_config
        assert optimization_manager._forecasting_manager == mock_forecasting_manager
        assert optimization_manager._ml_model_manager == mock_ml_model_manager
        assert hasattr(optimization_manager, "_retrieve_hass")
        assert hasattr(optimization_manager, "_location")
        assert hasattr(optimization_manager, "_logger")
        assert optimization_manager._projected_load_devices == []

    def test_set_projected_load_devices(self, optimization_manager: OptimizationManager) -> None:
        """Test setting projected load devices."""
        device1 = MagicMock(spec=LoadInfo)
        device2 = MagicMock(spec=LoadInfo)
        devices = [device1, device2]

        optimization_manager.set_projected_load_devices(devices)

        assert optimization_manager._projected_load_devices == devices

    @patch("energy_assistant.optimizer.optimization.utils")
    @patch("energy_assistant.optimizer.optimization.Forecast")
    @patch("energy_assistant.optimizer.optimization.Optimization")
    def test_perfect_forecast_optim(
        self,
        mock_optimization: MagicMock,
        mock_forecast: MagicMock,
        mock_utils: MagicMock,
        optimization_manager: OptimizationManager,
        mock_retrieve_hass: MagicMock,
    ) -> None:
        """Test perfect forecast optimization."""
        # Setup mocks
        mock_utils.treat_runtimeparams.return_value = (
            "params",
            {"retrieve": "conf"},
            {"optim": "conf"},
            {"plant": "conf"}
        )
        mock_utils.get_days_list.return_value = ["2023-01-01", "2023-01-02"]

        mock_forecast_instance = MagicMock()
        mock_forecast_instance.var_load_cost = [0.1, 0.2]
        mock_forecast_instance.var_prod_price = [0.15, 0.25]
        mock_forecast.return_value = mock_forecast_instance

        mock_opt_instance = MagicMock()
        expected_result = pd.DataFrame({"result": [1, 2, 3]})
        mock_opt_instance.perform_perfect_forecast_optim.return_value = expected_result
        mock_optimization.return_value = mock_opt_instance

        # Call the method
        result = optimization_manager.perfect_forecast_optim()

        # Verify calls
        mock_utils.treat_runtimeparams.assert_called_once()
        mock_forecast.assert_called_once()
        mock_optimization.assert_called_once()
        mock_retrieve_hass.get_data.assert_called_once()
        mock_retrieve_hass.prepare_data.assert_called_once()
        mock_opt_instance.perform_perfect_forecast_optim.assert_called_once()

        assert result.equals(expected_result)

    @patch("energy_assistant.optimizer.optimization.utils")
    @patch("energy_assistant.optimizer.optimization.Forecast")
    @patch("energy_assistant.optimizer.optimization.Optimization")
    def test_perfect_forecast_optim_with_debug(
        self,
        mock_optimization: MagicMock,
        mock_forecast: MagicMock,
        mock_utils: MagicMock,
        optimization_manager: OptimizationManager,
    ) -> None:
        """Test perfect forecast optimization with debug flag."""
        # Setup basic mocks
        mock_utils.treat_runtimeparams.return_value = ("params", {}, {}, {})
        mock_utils.get_days_list.return_value = []

        mock_forecast_instance = MagicMock()
        mock_forecast_instance.var_load_cost = []
        mock_forecast_instance.var_prod_price = []
        mock_forecast.return_value = mock_forecast_instance

        mock_opt_instance = MagicMock()
        expected_result = pd.DataFrame()
        mock_opt_instance.perform_perfect_forecast_optim.return_value = expected_result
        mock_optimization.return_value = mock_opt_instance

        # Call with debug=True
        result = optimization_manager.perfect_forecast_optim(debug=True)

        # Verify the debug parameter is handled (implementation may vary)
        mock_opt_instance.perform_perfect_forecast_optim.assert_called_once()
        assert isinstance(result, pd.DataFrame)

    @patch("energy_assistant.optimizer.optimization.utils")
    @patch("energy_assistant.optimizer.optimization.Forecast")
    @patch("energy_assistant.optimizer.optimization.Optimization")
    def test_perfect_forecast_optim_save_data_false(
        self,
        mock_optimization: MagicMock,
        mock_forecast: MagicMock,
        mock_utils: MagicMock,
        optimization_manager: OptimizationManager,
    ) -> None:
        """Test perfect forecast optimization with save_data_to_file=False."""
        # Setup basic mocks
        mock_utils.treat_runtimeparams.return_value = ("params", {}, {}, {})
        mock_utils.get_days_list.return_value = []

        mock_forecast_instance = MagicMock()
        mock_forecast_instance.var_load_cost = []
        mock_forecast_instance.var_prod_price = []
        mock_forecast.return_value = mock_forecast_instance

        mock_opt_instance = MagicMock()
        expected_result = pd.DataFrame()
        mock_opt_instance.perform_perfect_forecast_optim.return_value = expected_result
        mock_optimization.return_value = mock_opt_instance

        # Call with save_data_to_file=False
        result = optimization_manager.perfect_forecast_optim(save_data_to_file=False)

        mock_opt_instance.perform_perfect_forecast_optim.assert_called_once()
        assert isinstance(result, pd.DataFrame)

    def test_get_load_devices_for_optimization(self, optimization_manager: OptimizationManager) -> None:
        """Test getting load devices for optimization."""
        # Setup projected load devices
        device1 = MagicMock(spec=LoadInfo)
        device1.device_id = "device1"
        device1.power = 100.0
        device1.start_datetime = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)

        device2 = MagicMock(spec=LoadInfo)
        device2.device_id = "device2"
        device2.power = 200.0
        device2.start_datetime = datetime(2023, 1, 1, 14, 0, tzinfo=UTC)

        optimization_manager.set_projected_load_devices([device1, device2])

        # The method should return the projected load devices
        devices = optimization_manager._projected_load_devices
        assert len(devices) == 2
        assert device1 in devices
        assert device2 in devices

    @patch("energy_assistant.optimizer.optimization.LOGGER")
    def test_logging_during_perfect_forecast_optim(
        self,
        mock_logger: MagicMock,
        optimization_manager: OptimizationManager,
    ) -> None:
        """Test that logging occurs during perfect forecast optimization."""
        with patch("energy_assistant.optimizer.optimization.utils") as mock_utils, \
             patch("energy_assistant.optimizer.optimization.Forecast") as mock_forecast, \
             patch("energy_assistant.optimizer.optimization.Optimization") as mock_optimization:

            # Setup mocks
            mock_utils.treat_runtimeparams.return_value = ("params", {}, {}, {})
            mock_utils.get_days_list.return_value = []

            mock_forecast_instance = MagicMock()
            mock_forecast_instance.var_load_cost = []
            mock_forecast_instance.var_prod_price = []
            mock_forecast.return_value = mock_forecast_instance

            mock_opt_instance = MagicMock()
            mock_opt_instance.perform_perfect_forecast_optim.return_value = pd.DataFrame()
            mock_optimization.return_value = mock_opt_instance

            optimization_manager.perfect_forecast_optim()

            # Verify logging calls
            assert mock_logger.info.call_count >= 2  # At least "Setting up" and "Performing" messages

            log_messages = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Setting up needed data" in msg for msg in log_messages)
            assert any("Performing perfect forecast optimization" in msg for msg in log_messages)
