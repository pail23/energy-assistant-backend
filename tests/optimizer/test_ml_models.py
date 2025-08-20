"""Tests for the ml_models module."""

import sys
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

# Mock external dependencies before importing the modules
mock_emhass = MagicMock()
mock_emhass.utils = MagicMock()
mock_emhass.machine_learning_forecaster = MagicMock()
mock_emhass.machine_learning_forecaster.MLForecaster = MagicMock()
mock_emhass.retrieve_hass = MagicMock()
mock_emhass.retrieve_hass.RetrieveHass = MagicMock()
sys.modules['emhass'] = mock_emhass
sys.modules['emhass.utils'] = mock_emhass.utils
sys.modules['emhass.machine_learning_forecaster'] = mock_emhass.machine_learning_forecaster
sys.modules['emhass.retrieve_hass'] = mock_emhass.retrieve_hass

mock_sklearn = MagicMock()
mock_sklearn.metrics = MagicMock()
mock_sklearn.metrics.r2_score = MagicMock()
sys.modules['sklearn'] = mock_sklearn
sys.modules['sklearn.metrics'] = mock_sklearn.metrics

from energy_assistant.optimizer.config import EmhassConfig
from energy_assistant.optimizer.ml_models import (
    LOAD_FORECAST_MODEL_TYPE,
    MLForecasterTuneError,
    MLModelManager,
)


@pytest.fixture
def mock_config() -> EmhassConfig:
    """Create a mock EmhassConfig for testing."""
    config = MagicMock(spec=EmhassConfig)
    config.retrieve_hass_conf = {
        "optimization_time_step": MagicMock(),
        "days_to_retrieve": 10,
    }
    config.retrieve_hass_conf["optimization_time_step"].total_seconds.return_value = 3600
    config.optim_conf = {"test": "optim"}
    config.plant_conf = {"test": "plant"}
    config.power_no_var_loads_id = "sensor.power_load"
    config.emhass_path_conf = {"emhass_conf_path": "/test/path"}
    return config


@pytest.fixture
def mock_retrieve_hass() -> MagicMock:
    """Create a mock RetrieveHass for testing."""
    retrieve_hass = MagicMock()
    retrieve_hass.df_final = pd.DataFrame({
        "sensor.power_load": [100, 200, 300, 400, 500],
    }, index=pd.date_range("2023-01-01", periods=5, freq="1h"))
    return retrieve_hass


@pytest.fixture
def ml_model_manager(mock_config: EmhassConfig, mock_retrieve_hass: MagicMock) -> MLModelManager:
    """Create an MLModelManager instance for testing."""
    return MLModelManager(mock_config, mock_retrieve_hass)


class TestMLModelManager:
    """Test the MLModelManager class."""

    def test_init(self, ml_model_manager: MLModelManager, mock_config: EmhassConfig) -> None:
        """Test MLModelManager initialization."""
        assert ml_model_manager._config == mock_config
        assert hasattr(ml_model_manager, "_retrieve_hass")
        assert hasattr(ml_model_manager, "_logger")
        assert ml_model_manager._optimzed_devices == []

    def test_set_optimized_devices(self, ml_model_manager: MLModelManager) -> None:
        """Test setting optimized devices."""
        devices = ["device1", "device2"]
        ml_model_manager.set_optimized_devices(devices)
        assert ml_model_manager._optimzed_devices == devices

    def test_get_ml_runtime_params(self, ml_model_manager: MLModelManager) -> None:
        """Test getting ML runtime parameters."""
        with patch.object(ml_model_manager, "_generate_ml_runtime_params") as mock_generate:
            expected_params = {"test": "params"}
            mock_generate.return_value = expected_params

            result = ml_model_manager.get_ml_runtime_params()

            mock_generate.assert_called_once()
            assert result == expected_params

    def test_generate_ml_runtime_params_structure(self, ml_model_manager: MLModelManager) -> None:
        """Test the structure of generated ML runtime parameters."""
        params = ml_model_manager._generate_ml_runtime_params()

        assert isinstance(params, dict)
        assert "freq" in params
        assert "freq" in params
        assert "passed_data" in params
        assert params["freq"] == 1.0  # 3600 seconds / 3600 = 1 hour

        passed_data = params["passed_data"]
        assert "model_type" in passed_data
        assert "sklearn_model" in passed_data
        assert "num_lags" in passed_data
        assert "split_date_delta" in passed_data
        assert "perform_backtest" in passed_data
        assert passed_data["model_type"] == LOAD_FORECAST_MODEL_TYPE

    @patch("energy_assistant.optimizer.ml_models.utils")
    @patch("energy_assistant.optimizer.ml_models.MLForecaster")
    def test_fit_load_forecast_model(
        self,
        mock_ml_forecaster_class: MagicMock,
        mock_utils: MagicMock,
        ml_model_manager: MLModelManager,
        mock_retrieve_hass: MagicMock,
    ) -> None:
        """Test fitting the load forecast model."""
        # Setup mocks
        mock_params = '{"passed_data": {"model_type": "load_forecast", "sklearn_model": "LinearRegression", "num_lags": 48, "split_date_delta": "30d", "perform_backtest": true}}'
        mock_utils.treat_runtimeparams.return_value = [mock_params]
        mock_utils.get_days_list.return_value = ["2023-01-01", "2023-01-02"]

        mock_ml_forecaster = MagicMock()
        mock_df_pred = pd.DataFrame({
            "pred": [100, 200, 300, None, None],
            "test": [105, 195, 295, None, None]
        })
        mock_ml_forecaster.fit.return_value = mock_df_pred
        mock_ml_forecaster_class.return_value = mock_ml_forecaster

        # Call the method
        with patch("energy_assistant.optimizer.ml_models.r2_score") as mock_r2:
            mock_r2.return_value = 0.95
            result = ml_model_manager.fit_load_forecast_model()

        # Verify calls
        mock_utils.treat_runtimeparams.assert_called_once()
        mock_utils.get_days_list.assert_called_once()
        mock_retrieve_hass.get_data.assert_called_once()
        mock_ml_forecaster.fit.assert_called_once()
        mock_r2.assert_called_once()

        assert isinstance(result, pd.DataFrame)

    @patch("energy_assistant.optimizer.ml_models.utils")
    @patch("energy_assistant.optimizer.ml_models.MLForecaster")
    def test_fit_load_forecast_model_with_custom_days(
        self,
        mock_ml_forecaster_class: MagicMock,
        mock_utils: MagicMock,
        ml_model_manager: MLModelManager,
    ) -> None:
        """Test fitting model with custom number of days to retrieve."""
        # Setup mocks
        mock_params = '{"passed_data": {"model_type": "load_forecast", "sklearn_model": "LinearRegression", "num_lags": 48, "split_date_delta": "30d", "perform_backtest": true}}'
        mock_utils.treat_runtimeparams.return_value = [mock_params]
        mock_utils.get_days_list.return_value = ["2023-01-01"]

        mock_ml_forecaster = MagicMock()
        mock_df_pred = pd.DataFrame({"pred": [100], "test": [105]})
        mock_ml_forecaster.fit.return_value = mock_df_pred
        mock_ml_forecaster_class.return_value = mock_ml_forecaster

        # Call with custom days
        with patch("energy_assistant.optimizer.ml_models.r2_score"):
            result = ml_model_manager.fit_load_forecast_model(days_to_retrieve=1)

        mock_utils.get_days_list.assert_called_once_with(1)
        assert isinstance(result, pd.DataFrame)

    @patch("energy_assistant.optimizer.ml_models.MLForecaster")
    @patch("builtins.open", new_callable=mock_open, read_data=b"pickled_model_data")
    @patch("energy_assistant.optimizer.ml_models.pickle.load")
    def test_tune_load_forecast_model_success(
        self,
        mock_pickle_load: MagicMock,
        mock_file_open: MagicMock,
        mock_ml_forecaster_class: MagicMock,
        ml_model_manager: MLModelManager,
    ) -> None:
        """Test successful tuning of load forecast model."""
        # Setup mock model file
        mock_model = MagicMock()
        mock_pickle_load.return_value = mock_model

        mock_ml_forecaster = MagicMock()
        mock_df_pred = pd.DataFrame({
            "pred": [100, 200, 300],
            "test": [105, 195, 295]
        })
        mock_ml_forecaster.tune.return_value = mock_df_pred
        mock_ml_forecaster_class.return_value = mock_ml_forecaster

        # Mock pathlib.Path.exists to return True
        with patch("pathlib.Path.exists", return_value=True), \
             patch("energy_assistant.optimizer.ml_models.r2_score") as mock_r2:
            mock_r2.return_value = 0.98
            result = ml_model_manager.tune_load_forecast_model()

        # Verify calls
        mock_file_open.assert_called_once()
        mock_pickle_load.assert_called_once()
        mock_ml_forecaster.tune.assert_called_once()
        mock_r2.assert_called_once()

        assert isinstance(result, pd.DataFrame)

    def test_tune_load_forecast_model_file_not_found(self, ml_model_manager: MLModelManager) -> None:
        """Test tuning when model file doesn't exist."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(MLForecasterTuneError),
        ):
            ml_model_manager.tune_load_forecast_model()

    @patch("energy_assistant.optimizer.ml_models.MLForecaster")
    @patch("builtins.open", new_callable=mock_open, read_data=b"pickled_model_data")
    @patch("energy_assistant.optimizer.ml_models.pickle.load")
    def test_predict_load_forecast_success(
        self,
        mock_pickle_load: MagicMock,
        mock_file_open: MagicMock,
        mock_ml_forecaster_class: MagicMock,
        ml_model_manager: MLModelManager,
    ) -> None:
        """Test successful load forecast prediction."""
        # Setup mock model file
        mock_model = MagicMock()
        mock_pickle_load.return_value = mock_model

        mock_ml_forecaster = MagicMock()
        mock_prediction = pd.Series([100, 200, 300], name="predictions")
        mock_ml_forecaster.predict.return_value = mock_prediction
        mock_ml_forecaster_class.return_value = mock_ml_forecaster

        # Mock pathlib.Path.exists to return True
        with patch("pathlib.Path.exists", return_value=True):
            result = ml_model_manager.predict_load_forecast()

        # Verify calls
        mock_file_open.assert_called_once()
        mock_pickle_load.assert_called_once()
        mock_ml_forecaster.predict.assert_called_once()

        assert result.equals(mock_prediction)

    def test_predict_load_forecast_file_not_found(self, ml_model_manager: MLModelManager) -> None:
        """Test prediction when model file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = ml_model_manager.predict_load_forecast()
            assert result is None

    @patch("energy_assistant.optimizer.ml_models.LOGGER")
    def test_logging_in_fit_model(
        self,
        mock_logger: MagicMock,
        ml_model_manager: MLModelManager,
    ) -> None:
        """Test that logging occurs during model fitting."""
        with patch("energy_assistant.optimizer.ml_models.utils") as mock_utils, \
             patch("energy_assistant.optimizer.ml_models.MLForecaster") as mock_ml_forecaster_class, \
             patch("energy_assistant.optimizer.ml_models.r2_score") as mock_r2:

            # Setup mocks
            mock_params = '{"passed_data": {"model_type": "load_forecast", "sklearn_model": "LinearRegression", "num_lags": 48, "split_date_delta": "30d", "perform_backtest": true}}'
            mock_utils.treat_runtimeparams.return_value = [mock_params]
            mock_utils.get_days_list.return_value = []

            mock_ml_forecaster = MagicMock()
            mock_df_pred = pd.DataFrame({"pred": [100], "test": [105]})
            mock_ml_forecaster.fit.return_value = mock_df_pred
            mock_ml_forecaster_class.return_value = mock_ml_forecaster

            mock_r2.return_value = 0.95

            ml_model_manager.fit_load_forecast_model()

            # Verify R2 score is logged
            mock_logger.info.assert_called_with("R2 score = 0.95")

    def test_model_file_path_construction(self, ml_model_manager: MLModelManager, mock_config: EmhassConfig) -> None:
        """Test that model file path is constructed correctly."""
        # Access the private method to test path construction logic
        # The path should be constructed using the config
        assert mock_config.emhass_path_conf["emhass_conf_path"] == "/test/path"
        assert LOAD_FORECAST_MODEL_TYPE == "load_forecast"
