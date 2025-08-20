"""Tests for the main EmhassOptimizer class."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from energy_assistant.devices import LoadInfo, Location, StatesRepository
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import Homeassistant
from energy_assistant.optimizer.emhass_optimizer import EmhassOptimizer, OptimizerNotInitializedError
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
    hass.url = "http://localhost:8123/"
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
            "optimization_time_step": MagicMock()
        },
        "optim_conf": {},
    }
    config.emhass.as_dict.return_value["retrieve_hass_conf"]["optimization_time_step"].total_seconds.return_value = 3600
    return config


@pytest.fixture
def emhass_optimizer(
    mock_config_storage: ConfigStorage,
    mock_hass: Homeassistant,
    mock_location: Location,
) -> EmhassOptimizer:
    """Create an EmhassOptimizer instance for testing."""
    with patch("energy_assistant.optimizer.emhass_optimizer.pathlib.Path.mkdir"), \
         patch("energy_assistant.optimizer.emhass_optimizer.pathlib.Path.exists", return_value=False), \
         patch("energy_assistant.optimizer.emhass_optimizer.RetrieveHass"):
        return EmhassOptimizer("/test/data", mock_config_storage, mock_hass, mock_location)


class TestEmhassOptimizer:
    """Test the EmhassOptimizer class."""

    def test_init(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test EmhassOptimizer initialization."""
        assert hasattr(emhass_optimizer, "_config")
        assert hasattr(emhass_optimizer, "_forecasting_manager")
        assert hasattr(emhass_optimizer, "_ml_model_manager")
        assert hasattr(emhass_optimizer, "_optimization_manager")
        assert hasattr(emhass_optimizer, "_state_manager")
        assert isinstance(emhass_optimizer._pv, FloatDataBuffer)
        assert isinstance(emhass_optimizer._no_var_loads, FloatDataBuffer)
        assert emhass_optimizer._day_ahead_forecast is None
        assert emhass_optimizer._optimzed_devices == []
        assert emhass_optimizer._projected_load_devices == []

    def test_get_optimized_power_not_initialized(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test get_optimized_power when optimizer is not initialized."""
        device_id = uuid.uuid4()

        with pytest.raises(OptimizerNotInitializedError):
            emhass_optimizer.get_optimized_power(device_id)

    def test_get_optimized_power_with_forecast(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test get_optimized_power when forecast is available."""
        device_id = uuid.uuid4()

        # Set up a day ahead forecast
        mock_forecast = pd.DataFrame({
            f"P_deferrable_{device_id}": [100, 200, 300],
            "other_column": [1, 2, 3]
        })
        emhass_optimizer._day_ahead_forecast = mock_forecast

        # Mock the _get_forecast_value method
        with patch.object(emhass_optimizer, "_get_forecast_value", return_value=150.0) as mock_get_value:
            result = emhass_optimizer.get_optimized_power(device_id)

            mock_get_value.assert_called_once_with(f"P_deferrable_{device_id}")
            assert result == 150.0

    def test_update_repository_states_delegates_to_state_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that update_repository_states delegates to state manager."""
        mock_home = MagicMock(spec=Home)
        mock_state_repository = MagicMock(spec=StatesRepository)

        with patch.object(emhass_optimizer._state_manager, "update_repository_states") as mock_update:
            emhass_optimizer.update_repository_states(mock_home, mock_state_repository)

            mock_update.assert_called_once_with(
                mock_home,
                mock_state_repository,
                emhass_optimizer._no_var_loads,
                emhass_optimizer._get_forecast_value
            )

    def test_perfect_forecast_optim_delegates_to_optimization_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that perfect_forecast_optim delegates to optimization manager."""
        expected_result = pd.DataFrame({"test": [1, 2, 3]})

        with patch.object(emhass_optimizer._optimization_manager, "perfect_forecast_optim", return_value=expected_result) as mock_optim:
            result = emhass_optimizer.perfect_forecast_optim(save_data_to_file=True, debug=True)

            mock_optim.assert_called_once_with(True, True)
            assert result.equals(expected_result)

    def test_get_ml_runtime_params_delegates_to_ml_model_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that get_ml_runtime_params delegates to ML model manager."""
        expected_params = {"freq": 1.0, "passed_data": {}}

        with patch.object(emhass_optimizer._ml_model_manager, "get_ml_runtime_params", return_value=expected_params) as mock_get_params:
            result = emhass_optimizer.get_ml_runtime_params()

            mock_get_params.assert_called_once()
            assert result == expected_params

    @pytest.mark.asyncio
    async def test_async_dayahead_forecast_optim_delegates_and_stores_result(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that async_dayahead_forecast_optim delegates and stores result."""
        expected_result = pd.DataFrame({"forecast": [1, 2, 3]})

        with patch.object(emhass_optimizer._optimization_manager, "async_dayahead_forecast_optim") as mock_optim:
            mock_optim.return_value = expected_result

            await emhass_optimizer.async_dayahead_forecast_optim(save_data_to_file=True, debug=True)

            mock_optim.assert_called_once_with(True, True)
            assert emhass_optimizer._day_ahead_forecast.equals(expected_result)

    @pytest.mark.asyncio
    async def test_async_naive_mpc_optim_delegates_to_optimization_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that async_naive_mpc_optim delegates to optimization manager."""
        expected_result = pd.DataFrame({"mpc": [1, 2, 3]})

        with patch.object(emhass_optimizer._optimization_manager, "async_naive_mpc_optim") as mock_mpc:
            mock_mpc.return_value = expected_result

            result = await emhass_optimizer.async_naive_mpc_optim(save_data_to_file=True, debug=True)

            mock_mpc.assert_called_once_with(True, True)
            assert result.equals(expected_result)

    def test_forecast_model_fit_delegates_to_ml_model_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that forecast_model_fit delegates to ML model manager."""
        expected_result = 0.95

        with patch.object(emhass_optimizer._ml_model_manager, "forecast_model_fit", return_value=expected_result) as mock_fit:
            result = emhass_optimizer.forecast_model_fit(only_if_file_does_not_exist=True, days_to_retrieve=30)

            mock_fit.assert_called_once_with(True, 30)
            assert result == expected_result

    def test_forecast_model_tune_delegates_to_ml_model_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that forecast_model_tune delegates to ML model manager."""
        expected_result = 0.98

        with patch.object(emhass_optimizer._ml_model_manager, "forecast_model_tune", return_value=expected_result) as mock_tune:
            result = emhass_optimizer.forecast_model_tune()

            mock_tune.assert_called_once()
            assert result == expected_result

    def test_forecast_model_predict_delegates_to_ml_model_manager(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that forecast_model_predict delegates to ML model manager."""
        expected_result = pd.Series([100, 200, 300])

        with patch.object(emhass_optimizer._ml_model_manager, "forecast_model_predict", return_value=expected_result) as mock_predict:
            result = emhass_optimizer.forecast_model_predict()

            mock_predict.assert_called_once()
            assert result.equals(expected_result)

    def test_set_optimized_devices(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test setting optimized devices updates all managers."""
        devices = ["device1", "device2"]

        with patch.object(emhass_optimizer._ml_model_manager, "set_optimized_devices") as mock_ml_set, \
             patch.object(emhass_optimizer._state_manager, "set_optimized_devices") as mock_state_set:

            emhass_optimizer.set_optimized_devices(devices)

            mock_ml_set.assert_called_once_with(devices)
            mock_state_set.assert_called_once_with(devices)
            assert emhass_optimizer._optimzed_devices == devices

    def test_set_projected_load_devices(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test setting projected load devices updates optimization manager."""
        device1 = MagicMock(spec=LoadInfo)
        device2 = MagicMock(spec=LoadInfo)
        devices = [device1, device2]

        with patch.object(emhass_optimizer._optimization_manager, "set_projected_load_devices") as mock_set:
            emhass_optimizer.set_projected_load_devices(devices)

            mock_set.assert_called_once_with(devices)
            assert emhass_optimizer._projected_load_devices == devices

    def test_get_forecast_value_with_forecast_available(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test _get_forecast_value when forecast data is available."""
        mock_forecast = pd.DataFrame({
            "P_PV": [100, 200, 300],
            "P_Load": [400, 500, 600]
        })
        emhass_optimizer._day_ahead_forecast = mock_forecast

        result = emhass_optimizer._get_forecast_value("P_PV")
        assert result == 100  # First value in the series

    def test_get_forecast_value_no_forecast_available(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test _get_forecast_value when no forecast data is available."""
        emhass_optimizer._day_ahead_forecast = None

        result = emhass_optimizer._get_forecast_value("P_PV")
        assert result == 0

    def test_get_forecast_value_column_not_found(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test _get_forecast_value when column is not found in forecast."""
        mock_forecast = pd.DataFrame({
            "P_Load": [400, 500, 600]
        })
        emhass_optimizer._day_ahead_forecast = mock_forecast

        result = emhass_optimizer._get_forecast_value("P_PV")
        assert result == 0

    def test_get_forecast_value_empty_forecast(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test _get_forecast_value when forecast is empty."""
        mock_forecast = pd.DataFrame()
        emhass_optimizer._day_ahead_forecast = mock_forecast

        result = emhass_optimizer._get_forecast_value("P_PV")
        assert result == 0

    def test_composition_pattern_usage(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that EmhassOptimizer uses composition pattern correctly."""
        # Verify all managers are properly composed
        assert hasattr(emhass_optimizer, "_config")
        assert hasattr(emhass_optimizer, "_forecasting_manager")
        assert hasattr(emhass_optimizer, "_ml_model_manager")
        assert hasattr(emhass_optimizer, "_optimization_manager")
        assert hasattr(emhass_optimizer, "_state_manager")

        # Verify they are separate instances (not None)
        assert emhass_optimizer._forecasting_manager is not None
        assert emhass_optimizer._ml_model_manager is not None
        assert emhass_optimizer._optimization_manager is not None
        assert emhass_optimizer._state_manager is not None

    def test_data_buffers_initialization(self, emhass_optimizer: EmhassOptimizer) -> None:
        """Test that data buffers are properly initialized."""
        assert isinstance(emhass_optimizer._pv, FloatDataBuffer)
        assert isinstance(emhass_optimizer._no_var_loads, FloatDataBuffer)

        # Test that buffers can accept data
        emhass_optimizer._pv.add_data_point(100.0)
        emhass_optimizer._no_var_loads.add_data_point(200.0)

    def test_optimizer_not_initialized_error_message(self) -> None:
        """Test the OptimizerNotInitializedError message."""
        error = OptimizerNotInitializedError()
        assert str(error) == "Optimizer forecast is not initialized."

    @patch("energy_assistant.optimizer.emhass_optimizer.pathlib.Path.mkdir")
    @patch("energy_assistant.optimizer.emhass_optimizer.pathlib.Path.exists", return_value=False)
    @patch("energy_assistant.optimizer.emhass_optimizer.RetrieveHass")
    def test_initialization_with_different_data_folder(
        self,
        mock_retrieve_hass: MagicMock,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_config_storage: ConfigStorage,
        mock_hass: Homeassistant,
        mock_location: Location,
    ) -> None:
        """Test initialization with different data folder."""
        data_folder = "/custom/data/path"
        optimizer = EmhassOptimizer(data_folder, mock_config_storage, mock_hass, mock_location)

        assert optimizer._data_folder == Path(data_folder)
        mock_mkdir.assert_called()
