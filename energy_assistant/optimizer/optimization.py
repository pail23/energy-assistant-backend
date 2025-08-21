"""Optimization algorithms for EMHASS optimizer."""

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

# Conditional imports for external dependencies
if TYPE_CHECKING:
    from emhass import utils  # type: ignore
    from emhass.forecast import Forecast  # type: ignore
    from emhass.optimization import Optimization  # type: ignore
    from emhass.retrieve_hass import RetrieveHass  # type: ignore
else:
    try:
        from emhass import utils  # type: ignore
        from emhass.forecast import Forecast  # type: ignore
        from emhass.optimization import Optimization  # type: ignore
        from emhass.retrieve_hass import RetrieveHass  # type: ignore
    except ImportError:
        utils = None  # type: ignore
        Forecast = None  # type: ignore
        Optimization = None  # type: ignore
        RetrieveHass = None  # type: ignore

from energy_assistant.constants import ROOT_LOGGER_NAME
from energy_assistant.devices import LoadInfo, Location
from energy_assistant.devices.analysis import create_timeseries_from_const

if TYPE_CHECKING:
    from .config import EmhassConfig
    from .forecasting import ForecastingManager
    from .ml_models import MLModelManager

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)


class OptimizationManager:
    """Handle optimization operations."""

    def __init__(
        self,
        config: "EmhassConfig",
        forecasting_manager: "ForecastingManager",
        ml_model_manager: "MLModelManager",
        retrieve_hass: RetrieveHass,
        location: Location,
    ) -> None:
        """Initialize optimization manager."""
        self._config = config
        self._forecasting_manager = forecasting_manager
        self._ml_model_manager = ml_model_manager
        self._retrieve_hass = retrieve_hass
        self._location = location
        self._logger = LOGGER
        self._projected_load_devices: list[LoadInfo] = []

    def set_projected_load_devices(self, devices: list[LoadInfo]) -> None:
        """Set the projected load devices."""
        self._projected_load_devices = devices

    def perfect_forecast_optim(self, save_data_to_file: bool = True, debug: bool = False) -> pd.DataFrame:
        """Perform a call to the perfect forecast optimization routine."""
        self._logger.info("Setting up needed data")

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            None,
            json.dumps(self._config.emhass_config),
            self._config.retrieve_hass_conf,
            self._config.optim_conf,
            self._config.plant_conf,
            "perfect-optim",
            self._logger,
        )  # type: ignore

        fcst = Forecast(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            params,
            self._config.emhass_path_conf,
            self._logger,
            get_data_from_file=False,
        )

        opt = Optimization(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._config.cost_fun,
            self._config.emhass_path_conf,
            self._logger,
        )

        days_list = utils.get_days_list(self._config.retrieve_hass_conf["days_to_retrieve"])
        var_list = [self._config.solar_power_id, self._config.power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list, minimal_response=False, significant_changes_only=False)
        self._retrieve_hass.prepare_data(
            self._config.retrieve_hass_conf["sensor_power_load_no_var_loads"],
            load_negative=self._config.retrieve_hass_conf["load_negative"],
            set_zero_min=self._config.retrieve_hass_conf["set_zero_min"],
            var_replace_zero=self._config.retrieve_hass_conf["sensor_replace_zero"],
            var_interp=self._config.retrieve_hass_conf["sensor_linear_interp"],
        )
        df_input_data = self._retrieve_hass.df_final.copy()

        self._logger.info("Performing perfect forecast optimization")
        # Load cost and prod price forecast
        df_input_data = fcst.get_load_cost_forecast(df_input_data, method=fcst.optim_conf["load_cost_forecast_method"])
        df_input_data = fcst.get_prod_price_forecast(
            df_input_data,
            method=fcst.optim_conf["prod_price_forecast_method"],
        )
        opt_res = opt.perform_perfect_forecast_optim(df_input_data, days_list)

        # Save CSV file for analysis
        if save_data_to_file:
            filename = f"opt_res_perfect_optim_{self._config.cost_fun}.csv"
        else:  # Just save the latest optimization results
            filename = "opt_res_perfect_optim_latest.csv"
        if not debug:
            opt_res.to_csv(self._config._data_folder / filename, index_label="timestamp")
        return opt_res

    async def async_dayahead_forecast_optim(
        self, save_data_to_file: bool = False, debug: bool = False
    ) -> pd.DataFrame | None:
        """Perform a call to the day-ahead optimization routine."""
        self._logger.info("Setting up needed data for a day ahead forecast")

        # Fall back to the naive method in case the model for the mlforecaster does not exist
        filename_path = self._config._data_folder / "load_forecast_mlf.pkl"
        if not filename_path.exists():
            self._config._optim_conf["load_forecast_method"] = "naive"
            self._logger.warning("Falling back to the naive load forecaster.")

        # Treat runtimeparams
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(self._ml_model_manager.get_ml_runtime_params()),
            json.dumps(self._config.emhass_config),
            self._config.retrieve_hass_conf,
            self._config.optim_conf,
            self._config.plant_conf,
            "dayahead-optim",
            self._logger,
            self._config.emhass_path_conf,
        )

        fcst = Forecast(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            params,
            self._config.emhass_path_conf,
            self._logger,
            get_data_from_file=False,
        )

        opt = Optimization(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._config.cost_fun,
            self._config.emhass_path_conf,
            self._logger,
        )

        pv_forecast = await self._forecasting_manager.async_get_pv_forecast(fcst)
        p_load_forecast, p_load_forecast_values = self._forecasting_manager.get_load_forecast(
            fcst, pv_forecast, self._config.optim_conf["load_forecast_method"]
        )

        freq = self._config.retrieve_hass_conf["optimization_time_step"]

        df_input_data_dayahead = pd.DataFrame(
            np.transpose(np.vstack([np.array(pv_forecast.values), p_load_forecast_values])),
            index=pv_forecast.index,
            columns=["P_PV_forecast", "P_non_deferrable_load_forecast"],
        )

        projected_load = None
        for load_info in self._projected_load_devices:
            if not load_info.is_deferrable:
                series = create_timeseries_from_const(
                    load_info.nominal_power,
                    pd.Timedelta(int(load_info.duration), "s"),
                    freq,
                )
                projected_load = series if projected_load is None else projected_load + series

        if projected_load is not None:
            projected_load = projected_load.tz_convert(self._location.get_time_zone())
            df_input_data_dayahead["P_projected_load"] = projected_load
            df_input_data_dayahead["P_projected_load"] = df_input_data_dayahead["P_projected_load"].fillna(0)
        else:
            df_input_data_dayahead["P_projected_load"] = 0

        df_input_data_dayahead["P_load_forecast"] = (
            df_input_data_dayahead["P_projected_load"] + df_input_data_dayahead["P_non_deferrable_load_forecast"]
        )
        p_load_forecast = df_input_data_dayahead["P_load_forecast"]
        df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)

        self._logger.info("Performing day-ahead forecast optimization")
        # Load cost and prod price forecast
        df_input_data_dayahead = fcst.get_load_cost_forecast(
            df_input_data_dayahead,
            method=fcst.optim_conf["load_cost_forecast_method"],
        )
        df_input_data_dayahead = fcst.get_prod_price_forecast(
            df_input_data_dayahead,
            method=fcst.optim_conf["production_price_forecast_method"],
        )

        day_ahead_forecast = opt.perform_dayahead_forecast_optim(
            df_input_data_dayahead,
            pv_forecast,
            p_load_forecast,
        )

        if day_ahead_forecast is not None:
            day_ahead_forecast["P_projected_load"] = df_input_data_dayahead["P_projected_load"].copy()

        if not debug and day_ahead_forecast is not None:
            # Save CSV file for publish_data
            if save_data_to_file:
                today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                filename = "opt_res_dayahead_" + today.strftime("%Y_%m_%d") + ".csv"
            else:  # Just save the latest optimization results
                filename = "opt_res_latest.csv"
            day_ahead_forecast.to_csv(self._config._data_folder / filename, index_label="timestamp")

        return day_ahead_forecast

    async def async_naive_mpc_optim(self, save_data_to_file: bool = False, debug: bool = False) -> pd.DataFrame:
        """Perform a call to the naive Model Predictive Controller optimization routine."""
        self._logger.info("Setting up needed data")

        runtimeparams: dict = {"prediction_horizon": 48}  # How many 30 min slots do we predict -> 24h

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(runtimeparams),
            json.dumps(self._config.emhass_config),
            self._config.retrieve_hass_conf,
            self._config.optim_conf,
            self._config.plant_conf,
            "naive-mpc-optim",
            self._logger,
        )  # type: ignore

        fcst = Forecast(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            params,
            self._config.emhass_path_conf,
            self._logger,
            get_data_from_file=False,
        )

        opt = Optimization(
            self._config.retrieve_hass_conf,
            optim_conf,
            plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._config.cost_fun,
            self._config.emhass_path_conf,
            self._logger,
        )

        # Retrieve data from hass
        days_list = utils.get_days_list(1)
        var_list = [self._config.solar_power_id, self._config.power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list, minimal_response=False, significant_changes_only=False)
        self._retrieve_hass.prepare_data(
            self._config.retrieve_hass_conf["varsensor_power_load_no_var_loads_load"],
            load_negative=self._config.retrieve_hass_conf["load_negative"],
            set_zero_min=self._config.retrieve_hass_conf["set_zero_min"],
            var_replace_zero=self._config.retrieve_hass_conf["sensor_replace_zero"],
            var_interp=self._config.retrieve_hass_conf["sensor_linear_interp"],
        )
        df_input_data = self._retrieve_hass.df_final.copy()

        # Get PV and load forecasts
        p_pv_forecast = await self._forecasting_manager.async_get_pv_forecast(
            fcst, set_mix_forecast=True, df_now=df_input_data
        )

        p_load_forecast = fcst.get_load_forecast(
            method=self._config.optim_conf["load_forecast_method"],
            set_mix_forecast=True,
            df_now=df_input_data,
        )
        df_input_data_dayahead = pd.concat(
            [
                pd.Series(p_pv_forecast, name="P_PV_forecast"),
                pd.Series(p_load_forecast, name="P_load_forecast"),
            ],
            axis=1,
        )
        df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)

        self._logger.info("Performing naive MPC optimization")
        # Load cost and prod price forecast
        df_input_data_dayahead = fcst.get_load_cost_forecast(
            df_input_data_dayahead,
            method=fcst.optim_conf["load_cost_forecast_method"],
        )
        df_input_data_dayahead = fcst.get_prod_price_forecast(
            df_input_data_dayahead,
            method=fcst.optim_conf["prod_price_forecast_method"],
        )

        # The specifics params for the MPC at runtime
        params_dict = json.loads(params)
        prediction_horizon = params_dict["passed_data"]["prediction_horizon"]
        soc_init = params_dict["passed_data"]["soc_init"]
        soc_final = params_dict["passed_data"]["soc_final"]
        def_total_hours = [1, 1]  # input_data_dict['params']['passed_data']['def_total_hours']

        opt_res_naive_mpc = opt.perform_naive_mpc_optim(
            df_input_data_dayahead,
            p_pv_forecast,
            p_load_forecast,
            prediction_horizon,
            soc_init,
            soc_final,
            def_total_hours,
        )

        # Save CSV file for publish_data
        if save_data_to_file:
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            filename = "opt_res_naive_mpc_" + today.strftime("%Y_%m_%d") + ".csv"
        else:  # Just save the latest optimization results
            filename = "opt_res_naive_mpc_latest.csv"
        if not debug:
            opt_res_naive_mpc.to_csv(self._config._data_folder / filename, index_label="timestamp")
        return opt_res_naive_mpc
