"""Tests for the forecasting module."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Mock external dependencies before importing the modules
mock_emhass = MagicMock()
mock_emhass.forecast = MagicMock()
mock_emhass.forecast.Forecast = MagicMock()
sys.modules["emhass"] = mock_emhass
sys.modules["emhass.forecast"] = mock_emhass.forecast

from energy_assistant.devices import Location
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.homeassistant import Homeassistant
from energy_assistant.optimizer.config import EmhassConfig
from energy_assistant.optimizer.forecasting import ForecastingManager


@pytest.fixture
def mock_config() -> EmhassConfig:
    """Create a mock EmhassConfig for testing."""
    config = MagicMock(spec=EmhassConfig)
    config.pv_forecast_method = "homeassistant"
    config.optim_conf = {"weather_forecast_method": "test_method"}
    return config


@pytest.fixture
def mock_hass() -> Homeassistant:
    """Create a mock Home Assistant for testing."""
    return MagicMock(spec=Homeassistant)


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
def mock_no_var_loads() -> FloatDataBuffer:
    """Create a mock no var loads buffer for testing."""
    buffer = MagicMock(spec=FloatDataBuffer)
    buffer.average.return_value = 1000.0  # 1kW average
    return buffer


@pytest.fixture
def forecasting_manager(
    mock_config: EmhassConfig,
    mock_hass: Homeassistant,
    mock_location: Location,
    mock_no_var_loads: FloatDataBuffer,
) -> ForecastingManager:
    """Create a ForecastingManager instance for testing."""
    return ForecastingManager(mock_config, mock_hass, mock_location, mock_no_var_loads)


class TestForecastingManager:
    """Test the ForecastingManager class."""

    def test_init(self, forecasting_manager: ForecastingManager, mock_config: EmhassConfig) -> None:
        """Test ForecastingManager initialization."""
        assert forecasting_manager._config == mock_config
        assert hasattr(forecasting_manager, "_hass")
        assert hasattr(forecasting_manager, "_location")
        assert hasattr(forecasting_manager, "_no_var_loads")
        assert hasattr(forecasting_manager, "_logger")

    @pytest.mark.asyncio
    async def test_async_get_pv_forecast_homeassistant_method(
        self,
        forecasting_manager: ForecastingManager,
        mock_config: EmhassConfig,
        mock_hass: Homeassistant,
    ) -> None:
        """Test PV forecast when using homeassistant method."""
        mock_config.pv_forecast_method = "homeassistant"

        # Set up mock configuration with proper frequency
        mock_config.retrieve_hass_conf = {"optimization_time_step": "30min"}

        # Create mock DataFrame with proper structure for pandas operations
        mock_forecast_data = pd.DataFrame(
            {"sum": [100, 200, 300, 400], "timestamp": pd.date_range("2023-01-01 00:00", periods=4, freq="h", tz="UTC")}
        )
        mock_forecast_data.set_index("timestamp", inplace=True)

        mock_hass.get_solar_forecast = AsyncMock(return_value=mock_forecast_data)

        mock_fcst = MagicMock()
        mock_fcst.forecast_dates = [
            pd.Timestamp("2023-01-01 01:00", tz="UTC"),
            pd.Timestamp("2023-01-01 03:00", tz="UTC"),
        ]

        result = await forecasting_manager.async_get_pv_forecast(mock_fcst)

        mock_hass.get_solar_forecast.assert_called_once()
        assert isinstance(result, pd.Series)

    @pytest.mark.asyncio
    async def test_async_get_pv_forecast_other_method(
        self,
        forecasting_manager: ForecastingManager,
        mock_config: EmhassConfig,
    ) -> None:
        """Test PV forecast when using other methods."""
        mock_config.pv_forecast_method = "solcast"

        mock_fcst = MagicMock()
        mock_weather_df = pd.DataFrame({"temp": [20, 25, 30]})
        mock_fcst.get_weather_forecast.return_value = mock_weather_df
        mock_power_series = pd.Series([100, 200, 300])
        mock_fcst.get_power_from_weather.return_value = mock_power_series

        result = await forecasting_manager.async_get_pv_forecast(mock_fcst, set_mix_forecast=True)

        mock_fcst.get_weather_forecast.assert_called_once_with(method="test_method")
        # Check that get_power_from_weather was called with the right arguments
        mock_fcst.get_power_from_weather.assert_called_once()
        call_args = mock_fcst.get_power_from_weather.call_args
        assert call_args[0][0].equals(mock_weather_df)  # df_weather parameter
        assert call_args[0][1] is True  # set_mix_forecast parameter
        assert isinstance(call_args[0][2], pd.DataFrame)  # df_now parameter
        assert result.equals(mock_power_series)

    @pytest.mark.asyncio
    async def test_async_get_pv_forecast_with_df_now(
        self,
        forecasting_manager: ForecastingManager,
        mock_config: EmhassConfig,
    ) -> None:
        """Test PV forecast with df_now parameter."""
        mock_config.pv_forecast_method = "solcast"

        mock_fcst = MagicMock()
        mock_weather_df = pd.DataFrame({"temp": [20, 25, 30]})
        mock_fcst.get_weather_forecast.return_value = mock_weather_df
        mock_power_series = pd.Series([100, 200, 300])
        mock_fcst.get_power_from_weather.return_value = mock_power_series

        df_now = pd.DataFrame({"current": [50]})

        result = await forecasting_manager.async_get_pv_forecast(mock_fcst, set_mix_forecast=False, df_now=df_now)

        mock_fcst.get_power_from_weather.assert_called_once_with(mock_weather_df, False, df_now)
        assert result.equals(mock_power_series)

    def test_get_load_forecast_with_ml_forecaster(
        self,
        forecasting_manager: ForecastingManager,
    ) -> None:
        """Test load forecast using ML forecaster."""
        pv_forecast = pd.Series([100, 200, 300], name="pv")

        # Create a mock fcst object
        mock_fcst = MagicMock()
        mock_p_load_forecast = pd.Series([500, 600, 700], index=pv_forecast.index)
        mock_fcst.get_load_forecast.return_value = mock_p_load_forecast

        result_series, result_values = forecasting_manager.get_load_forecast(mock_fcst, pv_forecast, "mlforecaster")

        mock_fcst.get_load_forecast.assert_called_once_with(method="mlforecaster")
        assert result_series.equals(mock_p_load_forecast)
        assert np.array_equal(result_values, np.array([500, 600, 700]))

    def test_get_load_forecast_with_ml_forecaster_exception(
        self,
        forecasting_manager: ForecastingManager,
        mock_no_var_loads: FloatDataBuffer,
    ) -> None:
        """Test load forecast when ML forecaster raises an exception."""
        pv_forecast = pd.Series([100, 200, 300], name="pv")

        # Create a mock fcst that raises an exception
        mock_fcst = MagicMock()
        mock_fcst.get_load_forecast.side_effect = Exception("Prediction failed")

        result_series, result_values = forecasting_manager.get_load_forecast(mock_fcst, pv_forecast, "mlforecaster")

        mock_fcst.get_load_forecast.assert_called_once_with(method="mlforecaster")
        mock_no_var_loads.average.assert_called_once()

        # Should fall back to average values
        expected_values = [1000.0, 1000.0, 1000.0]
        assert result_series.tolist() == expected_values
        assert np.array_equal(result_values, np.array(expected_values))
        assert result_series.index.equals(pv_forecast.index)

    def test_get_load_forecast_without_ml_forecaster(
        self,
        forecasting_manager: ForecastingManager,
        mock_no_var_loads: FloatDataBuffer,
    ) -> None:
        """Test load forecast without ML forecaster."""
        pv_forecast = pd.Series([100, 200, 300], name="pv")

        # Create a mock fcst that returns None (simulating no ML forecaster)
        mock_fcst = MagicMock()
        mock_fcst.get_load_forecast.side_effect = Exception("No forecaster available")

        result_series, result_values = forecasting_manager.get_load_forecast(mock_fcst, pv_forecast, "mlforecaster")

        mock_no_var_loads.average.assert_called_once()

        # Should use average values
        expected_values = [1000.0, 1000.0, 1000.0]
        assert result_series.tolist() == expected_values
        assert np.array_equal(result_values, np.array(expected_values))
        assert result_series.index.equals(pv_forecast.index)

    def test_get_load_forecast_logs_warning_on_exception(
        self,
        forecasting_manager: ForecastingManager,
        mock_no_var_loads: FloatDataBuffer,
    ) -> None:
        """Test that exception during load forecast is logged."""
        pv_forecast = pd.Series([100, 200, 300], name="pv")

        # Create a mock fcst that raises an exception
        mock_fcst = MagicMock()
        mock_fcst.get_load_forecast.side_effect = Exception("Prediction failed")

        # Patch the logger on the instance
        with patch.object(forecasting_manager, "_logger") as mock_logger:
            forecasting_manager.get_load_forecast(mock_fcst, pv_forecast, "mlforecaster")

            mock_logger.warning.assert_called_once()
            warning_message = mock_logger.warning.call_args[0][0]
            assert "Forecasting the load failed" in warning_message
        assert "missing history data" in warning_message
