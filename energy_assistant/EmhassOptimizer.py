"""Mqtt connection for energy assistant."""

import copy
from datetime import datetime, timezone
import json
import logging
import pathlib
import pickle
from typing import Tuple
import uuid

from emhass import utils  # type: ignore
from emhass.forecast import forecast  # type: ignore
from emhass.machine_learning_forecaster import mlforecaster  # type: ignore
from emhass.optimization import optimization  # type: ignore
from emhass.retrieve_hass import retrieve_hass  # type: ignore
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score  # type: ignore

from energy_assistant import Optimizer
from energy_assistant.devices import Location, StateId, StatesRepository
from energy_assistant.devices.analysis import DataBuffer
from energy_assistant.devices.config import EnergyAssistantConfig
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import HOMEASSISTANT_CHANNEL, Homeassistant
from energy_assistant.models.forecast import ForecastSchema, ForecastSerieSchema

from .constants import ROOT_LOGGER_NAME

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)

SENSOR_POWER_NO_VAR_LOADS = "power_load_no_var_loads"
DEFAULT_HASS_ENTITY_PREFIX = "em"
DEFAULT_COST_FUNC = "profit"
LOAD_FORECAST_MODEL_TYPE = "load_forecast"


class EmhassOptimizer(Optimizer):
    """Optimizer based on Emhass."""

    def __init__(
        self, data_folder: str, config: EnergyAssistantConfig, hass: Homeassistant
    ) -> None:
        """Create an emhass optimizer instance."""
        self._data_folder: pathlib.Path = pathlib.Path(data_folder)
        self._logger = LOGGER
        self._hass_url: str = hass.url
        if self._hass_url is not None and self._hass_url[-1] != "/":
            self._hass_url = self._hass_url + "/"
        self._hass_token: str = hass.token
        self._location: Location = config.location

        home_config = config.energy_assistant_config.get("home")
        self._solar_power_id: str | None = None
        if home_config is not None:
            self._solar_power_id = home_config.get("solar_power")
        self._emhass_config: dict | None = config.emhass_config
        self._power_no_var_loads_id = (
            f"sensor.{DEFAULT_HASS_ENTITY_PREFIX}_{SENSOR_POWER_NO_VAR_LOADS}"
        )
        if self._emhass_config is not None:
            self._cost_fun = self._emhass_config.get("costfun", DEFAULT_COST_FUNC)
            self._hass_entity_prefix = self._emhass_config.get(
                "hass_entity_prefix", DEFAULT_HASS_ENTITY_PREFIX
            )
            self._power_no_var_loads_id = (
                f"sensor.{self._hass_entity_prefix}_{SENSOR_POWER_NO_VAR_LOADS}"
            )
            params = json.dumps(self._emhass_config)
            retrieve_hass_conf, optim_conf, plant_conf = utils.get_yaml_parse(
                pathlib.Path(), False, params=params
            )
            # Patch variables with Energy Assistant Config
            retrieve_hass_conf["hass_url"] = self._hass_url
            retrieve_hass_conf["long_lived_token"] = self._hass_token
            retrieve_hass_conf["var_PV"] = self._solar_power_id
            if "var_load" not in retrieve_hass_conf:
                retrieve_hass_conf["var_load"] = self._power_no_var_loads_id
            else:
                self._power_no_var_loads_id = retrieve_hass_conf["var_load"]
            retrieve_hass_conf["var_replace_zero"] = [self._solar_power_id]
            retrieve_hass_conf["var_interp"] = [
                self._solar_power_id,
                self._power_no_var_loads_id,
            ]

            retrieve_hass_conf["time_zone"] = self._location.get_time_zone()
            retrieve_hass_conf["lat"] = self._location.latitude
            retrieve_hass_conf["lon"] = self._location.longitude
            retrieve_hass_conf["alt"] = self._location.elevation

            optim_conf["num_def_loads"] = 0

            self._retrieve_hass_conf = retrieve_hass_conf
            self._optim_conf = optim_conf
            self._plant_conf = plant_conf

            self._method_ts_round = retrieve_hass_conf.get("method_ts_round")

            # Define main objects
            self._retrieve_hass = retrieve_hass(
                self._hass_url,
                self._hass_token,
                retrieve_hass_conf["freq"],
                self._location.get_time_zone(),
                params,
                self._data_folder,
                self._logger,
                get_data_from_file=False,
            )  # type: ignore

        if self._cost_fun is None:
            self._cost_fun = "profit"
        if self._method_ts_round is None:
            self._method_ts_round = "nearest"

        self._day_ahead_forecast: pd.DataFrame | None = None
        self._optimzed_devices: list = []
        self._pv: DataBuffer = DataBuffer()
        self._no_var_loads: DataBuffer = DataBuffer()

    def update_repository_states(self, home: Home, state_repository: StatesRepository) -> None:
        """Calculate the power of the non varibale/non controllable loads."""
        power = home.home_consumption_power
        for device in home.devices:
            if device.power_controllable:
                power = power - device.power
        if power < 0:
            power = 0.0
        self._no_var_loads.add_data_point(power)
        attributes = {
            "unit_of_measurement": "W",
            "state_class": "measurement",
            "device_class": "power",
        }
        state_repository.set_state(
            StateId(id=self._power_no_var_loads_id, channel=HOMEASSISTANT_CHANNEL),
            str(power),
            attributes,
        )
        state_repository.set_state(
            StateId(id=f"sensor.{self._hass_entity_prefix}_p_pv", channel=HOMEASSISTANT_CHANNEL),
            str(self._get_forecast_value("P_PV")),
            attributes,
        )
        state_repository.set_state(
            StateId(
                id=f"sensor.{self._hass_entity_prefix}_p_consumption", channel=HOMEASSISTANT_CHANNEL
            ),
            str(self._get_forecast_value("P_Load")),
            attributes,
        )

    def perfect_forecast_optim(
        self, save_data_to_file: bool = True, debug: bool = False
    ) -> pd.DataFrame:
        """Perform a call to the perfect forecast optimization routine.

        :param input_data_dict:  A dictionnary with multiple data used by the action functions
        :type input_data_dict: dict
        :param logger: The passed logger object
        :type logger: logging object
        :param save_data_to_file: Save optimization results to CSV file
        :type save_data_to_file: bool, optional
        :param debug: A debug option useful for unittests
        :type debug: bool, optional
        :return: The output data of the optimization
        :rtype: pd.DataFrame

        """
        self._logger.info("Setting up needed data")

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            None,
            json.dumps(self._emhass_config),
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            "perfect-optim",
            self._logger,
        )  # type: ignore
        fcst = forecast(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            params,
            str(self._data_folder),
            self._logger,
            get_data_from_file=False,
        )
        opt = optimization(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._cost_fun,
            str(self._data_folder),
            self._logger,
        )

        days_list = utils.get_days_list(self._retrieve_hass_conf["days_to_retrieve"])
        var_list = [self._solar_power_id, self._power_no_var_loads_id]
        self._retrieve_hass.get_data(
            days_list, var_list, minimal_response=False, significant_changes_only=False
        )
        self._retrieve_hass.prepare_data(
            self._retrieve_hass_conf["var_load"],
            load_negative=self._retrieve_hass_conf["load_negative"],
            set_zero_min=self._retrieve_hass_conf["set_zero_min"],
            var_replace_zero=self._retrieve_hass_conf["var_replace_zero"],
            var_interp=self._retrieve_hass_conf["var_interp"],
        )
        df_input_data = self._retrieve_hass.df_final.copy()

        self._logger.info("Performing perfect forecast optimization")
        # Load cost and prod price forecast
        df_input_data = fcst.get_load_cost_forecast(
            df_input_data, method=fcst.optim_conf["load_cost_forecast_method"]
        )
        df_input_data = fcst.get_prod_price_forecast(
            df_input_data, method=fcst.optim_conf["prod_price_forecast_method"]
        )
        opt_res = opt.perform_perfect_forecast_optim(df_input_data, days_list)
        # Save CSV file for analysis
        if save_data_to_file:
            filename = f"opt_res_perfect_optim_{self._cost_fun}.csv"
        else:  # Just save the latest optimization results
            filename = "opt_res_perfect_optim_latest.csv"
        if not debug:
            opt_res.to_csv(self._data_folder / filename, index_label="timestamp")
        return opt_res

    def get_ml_runtime_params(self) -> dict:
        """Get the emhass runtime params for the machine learning load prediction."""
        freq = self._retrieve_hass_conf["freq"].total_seconds() / 3600

        runtimeparams: dict = {
            "num_def_loads": len(self._optimzed_devices),
            "P_deferrable_nom": [device.nominal_power for device in self._optimzed_devices],
            "def_total_hours": [device.deferrable_hours for device in self._optimzed_devices],
            "treat_def_as_semi_cont": [
                not device.is_continous for device in self._optimzed_devices
            ],
            "set_def_constant": [device.is_constant for device in self._optimzed_devices],
            "days_to_retrieve": self._retrieve_hass_conf.get("days_to_retrieve", 10),
            "model_type": LOAD_FORECAST_MODEL_TYPE,
            "var_model": self._power_no_var_loads_id,
            "sklearn_model": "KNeighborsRegressor",
            "num_lags": int(24 / freq),  # should be one day * 30 min
            "split_date_delta": "48h",
            "perform_backtest": True,
        }
        return runtimeparams

    def dayahead_forecast_optim(self, save_data_to_file: bool = False, debug: bool = False) -> None:
        """Perform a call to the day-ahead optimization routine.

        :param save_data_to_file: Save optimization results to CSV file
        :type save_data_to_file: bool, optional
        :param debug: A debug option useful for unittests
        :type debug: bool, optional

        """
        self._logger.info("Setting up needed data for a day ahead forecast")

        # Fall back to the naive method in case the model for the mlforecaster does not exist
        filename_path = self._data_folder / "load_forecast_mlf.pkl"
        if not filename_path.exists():
            self._optim_conf["load_forecast_method"] = "naive"
            self._logger.warning("Falling back to the naive load forecaster.")

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(self.get_ml_runtime_params()),
            json.dumps(self._emhass_config),
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            "dayahead-optim",
            self._logger,
        )  # type: ignore
        fcst = forecast(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            params,
            str(self._data_folder),
            self._logger,
            get_data_from_file=False,
        )
        opt = optimization(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._cost_fun,
            str(self._data_folder),
            self._logger,
        )

        df_weather = fcst.get_weather_forecast(method=self._optim_conf["weather_forecast_method"])
        P_PV_forecast = fcst.get_power_from_weather(df_weather)
        try:
            P_load_forecast = fcst.get_load_forecast(
                method=self._optim_conf["load_forecast_method"]
            )
            P_load_forecast_values = np.array(P_load_forecast.values)
        except Exception:
            self._logger.warning(
                "Forcasting the load failed, probably due to missing history data in Home Assistant."
            )
            avg_non_var_power = self._no_var_loads.average()
            P_load_forecast = pd.Series(
                [avg_non_var_power for x in P_PV_forecast.values],
                index=P_PV_forecast.index,
            )
            P_load_forecast_values = np.array([avg_non_var_power for x in P_PV_forecast.values])

        df_input_data_dayahead = pd.DataFrame(
            np.transpose(np.vstack([np.array(P_PV_forecast.values), P_load_forecast_values])),
            index=P_PV_forecast.index,
            columns=["P_PV_forecast", "P_load_forecast"],
        )
        df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)

        # params_dayahead: dict = json.loads(params)
        # if 'prediction_horizon' in params_dayahead['passed_data'] and params_dayahead['passed_data']['prediction_horizon'] is not None:
        #    prediction_horizon = params_dayahead['passed_data']['prediction_horizon']
        #    df_input_data_dayahead = copy.deepcopy(df_input_data_dayahead)[df_input_data_dayahead.index[0]:df_input_data_dayahead.index[prediction_horizon-1]]

        self._logger.info("Performing day-ahead forecast optimization")
        # Load cost and prod price forecast
        df_input_data_dayahead = fcst.get_load_cost_forecast(
            df_input_data_dayahead, method=fcst.optim_conf["load_cost_forecast_method"]
        )
        df_input_data_dayahead = fcst.get_prod_price_forecast(
            df_input_data_dayahead, method=fcst.optim_conf["prod_price_forecast_method"]
        )
        self._day_ahead_forecast = opt.perform_dayahead_forecast_optim(
            df_input_data_dayahead, P_PV_forecast, P_load_forecast
        )
        # Save CSV file for publish_data
        if save_data_to_file:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            filename = "opt_res_dayahead_" + today.strftime("%Y_%m_%d") + ".csv"
        else:  # Just save the latest optimization results
            filename = "opt_res_latest.csv"
        if not debug and self._day_ahead_forecast is not None:
            self._day_ahead_forecast.to_csv(self._data_folder / filename, index_label="timestamp")

    def naive_mpc_optim(self, save_data_to_file: bool = False, debug: bool = False) -> pd.DataFrame:
        """Perform a call to the naive Model Predictive Controller optimization routine.

        :param input_data_dict:  A dictionnary with multiple data used by the action functions
        :type input_data_dict: dict
        :param logger: The passed logger object
        :type logger: logging object
        :param save_data_to_file: Save optimization results to CSV file
        :type save_data_to_file: bool, optional
        :param debug: A debug option useful for unittests
        :type debug: bool, optional
        :return: The output data of the optimization
        :rtype: pd.DataFrame

        """

        self._logger.info("Setting up needed data")

        runtimeparams: dict = {
            "prediction_horizon": 48  # How many 30 min slots do we predict -> 24h
        }

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(runtimeparams),
            json.dumps(self._emhass_config),
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            "naive-mpc-optim",
            self._logger,
        )  # type: ignore
        fcst = forecast(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            params,
            str(self._data_folder),
            self._logger,
            get_data_from_file=False,
        )
        opt = optimization(
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            fcst.var_load_cost,
            fcst.var_prod_price,
            self._cost_fun,
            str(self._data_folder),
            self._logger,
        )

        # Retrieve data from hass
        days_list = utils.get_days_list(1)
        var_list = [self._solar_power_id, self._power_no_var_loads_id]
        self._retrieve_hass.get_data(
            days_list, var_list, minimal_response=False, significant_changes_only=False
        )
        self._retrieve_hass.prepare_data(
            self._retrieve_hass_conf["var_load"],
            load_negative=self._retrieve_hass_conf["load_negative"],
            set_zero_min=self._retrieve_hass_conf["set_zero_min"],
            var_replace_zero=self._retrieve_hass_conf["var_replace_zero"],
            var_interp=self._retrieve_hass_conf["var_interp"],
        )
        df_input_data = self._retrieve_hass.df_final.copy()

        # Get PV and load forecasts
        df_weather = fcst.get_weather_forecast(method=self._optim_conf["weather_forecast_method"])
        P_PV_forecast = fcst.get_power_from_weather(
            df_weather, set_mix_forecast=True, df_now=df_input_data
        )
        P_load_forecast = fcst.get_load_forecast(
            method=self._optim_conf["load_forecast_method"],
            set_mix_forecast=True,
            df_now=df_input_data,
        )
        df_input_data_dayahead = pd.concat(
            [
                pd.Series(P_PV_forecast, name="P_PV_forecast"),
                pd.Series(P_load_forecast, name="P_load_forecast"),
            ],
            axis=1,
        )
        df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)

        # params_naive_mpc_optim: dict = json.loads(params)
        # if 'prediction_horizon' in params_naive_mpc_optim['passed_data'] and params_naive_mpc_optim['passed_data']['prediction_horizon'] is not None:
        #    prediction_horizon = params_naive_mpc_optim['passed_data']['prediction_horizon']
        #    df_input_data_dayahead = copy.deepcopy(df_input_data_dayahead)[df_input_data_dayahead.index[0]:df_input_data_dayahead.index[prediction_horizon-1]]

        self._logger.info("Performing naive MPC optimization")
        # Load cost and prod price forecast
        df_input_data_dayahead = fcst.get_load_cost_forecast(
            df_input_data_dayahead, method=fcst.optim_conf["load_cost_forecast_method"]
        )
        df_input_data_dayahead = fcst.get_prod_price_forecast(
            df_input_data_dayahead, method=fcst.optim_conf["prod_price_forecast_method"]
        )

        # The specifics params for the MPC at runtime
        # TODO: Make this real parameters
        params_dict = json.loads(params)
        prediction_horizon = params_dict["passed_data"]["prediction_horizon"]
        soc_init = params_dict["passed_data"]["soc_init"]
        soc_final = params_dict["passed_data"]["soc_final"]
        def_total_hours = [
            1,
            1,
        ]  #  input_data_dict['params']['passed_data']['def_total_hours']

        opt_res_naive_mpc = opt.perform_naive_mpc_optim(
            df_input_data_dayahead,
            P_PV_forecast,
            P_load_forecast,
            prediction_horizon,
            soc_init,
            soc_final,
            def_total_hours,
        )
        # Save CSV file for publish_data
        if save_data_to_file:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            filename = "opt_res_naive_mpc_" + today.strftime("%Y_%m_%d") + ".csv"
        else:  # Just save the latest optimization results
            filename = "opt_res_naive_mpc_latest.csv"
        if not debug:
            opt_res_naive_mpc.to_csv(self._data_folder / filename, index_label="timestamp")
        return opt_res_naive_mpc

    def forecast_model_fit(
        self, only_if_file_does_not_exist: bool = False, days_to_retrieve: int | None = None
    ) -> float:
        """Perform a forecast model fit from training data retrieved from Home Assistant."""

        filename = LOAD_FORECAST_MODEL_TYPE + "_mlf.pkl"
        filename_path = self._data_folder / filename

        if only_if_file_does_not_exist and filename_path.is_file():
            self._logger.info("Skip model creation")
            return 0

        self._logger.info("Setting up needed data")

        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(self.get_ml_runtime_params()),
            json.dumps(self._emhass_config),
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            "forecast-model-fit",
            self._logger,
        )  # type: ignore

        params_dict: dict = json.loads(params)
        # Retrieve data from hass
        if days_to_retrieve is None:
            days_to_retrieve = self._retrieve_hass_conf.get("days_to_retrieve", 10)

        days_list = utils.get_days_list(days_to_retrieve)
        var_list = [self._power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list)
        df_input_data = self._retrieve_hass.df_final.copy()

        data = copy.deepcopy(df_input_data)
        model_type = params_dict["passed_data"]["model_type"]
        sklearn_model = params_dict["passed_data"]["sklearn_model"]
        num_lags = params_dict["passed_data"]["num_lags"]
        split_date_delta = params_dict["passed_data"]["split_date_delta"]
        perform_backtest = params_dict["passed_data"]["perform_backtest"]
        # The ML forecaster object
        mlf = mlforecaster(
            data,
            model_type,
            self._power_no_var_loads_id,
            sklearn_model,
            num_lags,
            str(self._data_folder),
            self._logger,
        )
        # Fit the ML model
        df_pred, df_pred_backtest = mlf.fit(
            split_date_delta=split_date_delta, perform_backtest=perform_backtest
        )
        predictions = df_pred["pred"].dropna()
        test_data = df_pred["test"].dropna()
        r2 = r2_score(test_data, predictions)
        self._logger.info(f"R2 score = {r2}")
        # Save model
        with open(self._data_folder / filename, "wb") as outp:
            pickle.dump(mlf, outp, pickle.HIGHEST_PROTOCOL)
        return r2

    def forecast_model_tune(self) -> Tuple[pd.DataFrame, mlforecaster]:
        """Tune a forecast model hyperparameters using bayesian optimization.

        :param debug: True to debug, useful for unit testing, defaults to False
        :type debug: bool, optional
        :return: The DataFrame containing the forecast data results using the optimized model
        :rtype: pd.DataFrame
        """
        # Load model
        self._logger.info("Tune the forecast model")

        filename = LOAD_FORECAST_MODEL_TYPE + "_mlf.pkl"
        filename_path = self._data_folder / filename
        if filename_path.is_file():
            with open(filename_path, "rb") as inp:
                mlf = pickle.load(inp)
            # Tune the model
            df_pred_optim = mlf.tune(debug=False)

            # Save model
            with open(filename_path, "wb") as outp:
                pickle.dump(mlf, outp, pickle.HIGHEST_PROTOCOL)
            return df_pred_optim, mlf

        else:
            self._logger.error(
                "The ML forecaster file was not found, please run a model fit method before this tune method"
            )
            raise Exception(
                "The ML forecaster file was not found, please run a model fit method before this tune method"
            )

    def forecast_model_predict(
        self,
        use_last_window: bool = True,
        debug: bool = False,
        mlf: mlforecaster | None = None,
    ) -> pd.Series | None:
        """Perform a forecast model predict using a previously trained skforecast model.

        :param input_data_dict: A dictionnary with multiple data used by the action functions
        :type input_data_dict: dict
        :param logger: The passed logger object
        :type logger: logging.Logger
        :param use_last_window: True if the 'last_window' option should be used for the \
            custom machine learning forecast model. The 'last_window=True' means that the data \
            that will be used to generate the new forecast will be freshly retrieved from \
            Home Assistant. This data is needed because the forecast model is an auto-regressive \
            model with lags. If 'False' then the data using during the model train is used. Defaults to True
        :type use_last_window: Optional[bool], optional
        :param debug: True to debug, useful for unit testing, defaults to False
        :type debug: Optional[bool], optional
        :param mlf: The 'mlforecaster' object previously trained. This is mainly used for debug \
            and unit testing. In production the actual model will be read from a saved pickle file. Defaults to None
        :type mlf: Optional[mlforecaster], optional
        :return: The DataFrame containing the forecast prediction data
        :rtype: pd.DataFrame
        """
        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(self.get_ml_runtime_params()),
            json.dumps(self._emhass_config),
            self._retrieve_hass_conf,
            self._optim_conf,
            self._plant_conf,
            "forecast-model-fit",
            self._logger,
        )  # type: ignore

        params_dict: dict = json.loads(params)
        # Retrieve data from hass
        days_to_retrieve = params_dict["passed_data"]["days_to_retrieve"]

        days_list = utils.get_days_list(days_to_retrieve)
        var_list = [self._power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list)
        df_input_data = self._retrieve_hass.df_final.copy()

        # Load model
        model_type = "load_forecast"
        filename = model_type + "_mlf.pkl"
        filename_path = self._data_folder / filename
        if not debug:
            if filename_path.is_file():
                with open(filename_path, "rb") as inp:
                    mlf = pickle.load(inp)
            else:
                self._logger.error(
                    "The ML forecaster file was not found, please run a model fit method before this predict method"
                )
                return None
        # Make predictions
        if use_last_window:
            data_last_window = copy.deepcopy(df_input_data)
        else:
            data_last_window = None
        if mlf is not None:
            return mlf.predict(data_last_window)
        return None

    def get_forecast(self) -> ForecastSchema:
        """Get the previously calculated forecast."""
        if self._day_ahead_forecast is not None:
            freq = self._retrieve_hass_conf["freq"]
            temp_folder = self._data_folder / "temp"
            temp_folder.mkdir(parents=True, exist_ok=True)
            pv_df = self._pv.get_data_frame(freq, self._location.get_time_zone(), "pv", temp_folder)
            pv_df.to_csv(temp_folder / "pv_df.csv")
            no_var_load_df = self._no_var_loads.get_data_frame(
                freq, self._location.get_time_zone(), "non_var_loads", temp_folder
            )
            df = self._day_ahead_forecast.merge(
                pv_df, how="left", left_index=True, right_index=True
            )
            df = df.merge(no_var_load_df, how="left", left_index=True, right_index=True)

            df.rename(columns={"P_PV": "pv_forecast"}, inplace=True)
            df.to_csv(temp_folder / "forecast.csv", index_label="time_stamp")

            while not pd.notnull(df["pv_forecast"][0]) and len(df.index) > 0:
                df.drop(df.index[0], inplace=True)

            pv_series = [x for x in df["pv"].to_list() if pd.notnull(x)]
            no_var_load_series = [x for x in df["non_var_loads"].to_list() if pd.notnull(x)]

            # TODO: Should be removed
            df.fillna(-10000, inplace=True)
            time_series = df.index.to_series()
            time: list[datetime] = time_series.tolist()
            pv_forecast = df["pv_forecast"].to_list()
            load = df["P_Load"].to_list()
            cost_profit = df["cost_profit"].to_list()

            series = [
                ForecastSerieSchema(name="pv_forecast", data=pv_forecast),
                ForecastSerieSchema(name="pv", data=pv_series),
                ForecastSerieSchema(name="consumption", data=load),
                ForecastSerieSchema(name="no_var_loads", data=no_var_load_series),
                ForecastSerieSchema(name="cost_profit", data=cost_profit),
            ]
            consumed_energy = sum(load)
            for i, d in enumerate(self._optimzed_devices):
                device = self._day_ahead_forecast[f"P_deferrable{i}"].to_list()
                series.append(ForecastSerieSchema(name=str(d.device_id), data=device))
                consumed_energy = consumed_energy + sum(device)

            period = freq.total_seconds() / 3600
            solar_energy = sum(pv_forecast) * period / 1000  # kWh
            consumed_energy = consumed_energy * period / 1000  # kWh
            cost = sum(cost_profit)

            return ForecastSchema(
                solar_energy=solar_energy,
                cost=cost,
                consumed_energy=consumed_energy,
                time=time,
                series=series,
            )
        else:
            raise Exception("Optimizer forecast is not initialized.")

    def get_optimized_power(self, device_id: uuid.UUID) -> float:
        """Get the optimized power budget for a give device."""
        if self._day_ahead_forecast is not None:
            for i, deferrable_load_info in enumerate(self._optimzed_devices):
                if deferrable_load_info.device_id == device_id:
                    columnName = f"P_deferrable{i}"
                    return self._get_forecast_value(columnName)
        return -1

    def _get_forecast_value(self, columnName: str) -> float:
        """Get a forcasted value."""
        if self._day_ahead_forecast is not None:
            now_precise = datetime.now(self._location.get_time_zone()).replace(
                second=0, microsecond=0
            )
            if self._method_ts_round == "nearest":
                method = "nearest"
            elif self._method_ts_round == "first":
                method = "ffill"
            elif self._method_ts_round == "last":
                method = "bfill"
            else:
                method = "nearest"

            idx_closest = self._day_ahead_forecast.index.get_indexer([now_precise], method=method)[  # type: ignore
                0
            ]
            if idx_closest == -1:
                idx_closest = self._day_ahead_forecast.index.get_indexer(  # type: ignore
                    [now_precise], method="nearest"
                )[0]

            value = self._day_ahead_forecast.iloc[idx_closest][columnName]
            return float(value)
        return -1

    def _has_deferrable_load(self, device_id: uuid.UUID) -> bool:
        for deferrable_load_info in self._optimzed_devices:
            if deferrable_load_info.device_id == device_id:
                return True
        return False

    def update_devices(self, home: Home) -> None:
        """Update the selected devices from the list of devices."""
        new_optimizhed_devices = []
        needs_update = False
        self._pv.add_data_point(home.solar_production_power)
        for device in home.devices:
            deferrable_load_info = device.get_deferrable_load_info()
            if deferrable_load_info is not None:
                if not self._has_deferrable_load(device.id):
                    needs_update = True
                new_optimizhed_devices.append(deferrable_load_info)
            else:
                if self._has_deferrable_load(device.id):
                    needs_update = True
        self._optimzed_devices = new_optimizhed_devices
        if needs_update:
            self.dayahead_forecast_optim()
