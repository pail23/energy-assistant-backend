"""Forecasting logic for EMHASS optimizer."""

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

# Conditional import for emhass
if TYPE_CHECKING:
    from emhass.forecast import Forecast  # type: ignore
else:
    try:
        from emhass.forecast import Forecast  # type: ignore
    except ImportError:
        Forecast = None  # type: ignore

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices import Location
from energy_assistant.devices.analysis import FloatDataBuffer
from energy_assistant.devices.homeassistant import Homeassistant

if TYPE_CHECKING:
    from .config import EmhassConfig

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class ForecastingManager:
    """Handle PV and load forecasting operations."""

    def __init__(
        self,
        config: "EmhassConfig",
        hass: Homeassistant,
        location: Location,
        no_var_loads: FloatDataBuffer,
    ) -> None:
        """Initialize forecasting manager."""
        self._config = config
        self._hass = hass
        self._location = location
        self._no_var_loads = no_var_loads
        self._logger = LOGGER

    async def async_get_pv_forecast(
        self,
        fcst: Forecast,
        set_mix_forecast: bool | None = False,
        df_now: pd.DataFrame | None = None,
    ) -> pd.Series:
        """Get the PV forecast."""
        if self._config.pv_forecast_method != "homeassistant":
            df_weather = fcst.get_weather_forecast(method=self._config.optim_conf["weather_forecast_method"])
            if df_now is None:
                df_now = pd.DataFrame()
            return fcst.get_power_from_weather(df_weather, set_mix_forecast, df_now)

        pv_forecast_hourly = await self._hass.get_solar_forecast()
        freq = self._config.retrieve_hass_conf["optimization_time_step"]
        pv_forecast = pv_forecast_hourly.resample(freq).mean().interpolate()
        start = fcst.forecast_dates[0]
        end = fcst.forecast_dates[-1]
        pv_forecast_in_range = pv_forecast.loc[(pv_forecast.index >= start) & (pv_forecast.index <= end)]
        pv_forecast_serie = pv_forecast_in_range["sum"]
        pv_forecast_serie.index = pv_forecast_serie.index.tz_convert(self._location.get_time_zone())
        return pv_forecast_serie

    def get_load_forecast(
        self,
        fcst: Forecast,
        pv_forecast: pd.Series,
        load_forecast_method: str,
    ) -> tuple[pd.Series, np.ndarray]:
        """Get load forecast with fallback to naive method."""
        try:
            p_load_forecast = fcst.get_load_forecast(method=load_forecast_method)
            p_load_forecast_values = np.array(p_load_forecast.values)
        except Exception:
            self._logger.warning(
                "Forecasting the load failed, probably due to missing history data in Home Assistant. "
            )
            avg_non_var_power = self._no_var_loads.average()
            p_load_forecast = pd.Series(
                [avg_non_var_power for x in pv_forecast.values],
                index=pv_forecast.index,
            )
            p_load_forecast_values = np.array([avg_non_var_power for x in pv_forecast.values])

        return p_load_forecast, p_load_forecast_values
