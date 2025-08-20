"""Machine learning model management for EMHASS optimizer."""

import copy
import json
import logging
import pickle
from typing import TYPE_CHECKING, Any

import pandas as pd

# Conditional imports for external dependencies
if TYPE_CHECKING:
    from emhass import utils  # type: ignore
    from emhass.machine_learning_forecaster import MLForecaster  # type: ignore
    from emhass.retrieve_hass import RetrieveHass  # type: ignore
    from sklearn.metrics import r2_score  # type: ignore
else:
    try:
        from emhass import utils  # type: ignore
        from emhass.machine_learning_forecaster import MLForecaster  # type: ignore
        from emhass.retrieve_hass import RetrieveHass  # type: ignore
        from sklearn.metrics import r2_score  # type: ignore
    except ImportError:
        utils = None  # type: ignore
        MLForecaster = None  # type: ignore
        RetrieveHass = None  # type: ignore
        r2_score = None  # type: ignore

from energy_assistant.constants import ROOT_LOGGER_NAME

if TYPE_CHECKING:
    from .config import EmhassConfig

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)
LOAD_FORECAST_MODEL_TYPE = "load_forecast"


class MLForecasterTuneError(Exception):
    """Error while tuning the ML forecast."""

    def __init__(self) -> None:
        """Create an MLForecasterTuneError instance."""
        super().__init__("The ML forecaster file was not found, please run a model fit method before this tune method")


class MLModelManager:
    """Handle machine learning model operations."""

    def __init__(self, config: "EmhassConfig", retrieve_hass: RetrieveHass) -> None:
        """Initialize ML model manager."""
        self._config = config
        self._retrieve_hass = retrieve_hass
        self._logger = LOGGER
        self._optimzed_devices: list = []

    def set_optimized_devices(self, devices: list) -> None:
        """Set the optimized devices for ML parameter generation."""
        self._optimzed_devices = devices

    def get_ml_runtime_params(self) -> dict:
        """Get the emhass runtime params for the machine learning load prediction."""
        freq = self._config.retrieve_hass_conf["optimization_time_step"].total_seconds() / 3600

        runtimeparams: dict = {
            "number_of_deferrable_loads": len(self._optimzed_devices),
            "nominal_power_of_deferrable_loads": [device.nominal_power for device in self._optimzed_devices],
            "operating_hours_of_each_deferrable_load": [
                max(round(device.duration / 3600), 1) for device in self._optimzed_devices
            ],
            "start_timesteps_of_each_deferrable_load": [device.start_timestep for device in self._optimzed_devices],
            "end_timesteps_of_each_deferrable_load": [device.end_timestep for device in self._optimzed_devices],
            "treat_deferrable_load_as_semi_cont": [not device.is_continous for device in self._optimzed_devices],
            "set_deferrable_load_single_constant": [device.is_constant for device in self._optimzed_devices],
            "days_to_retrieve": self._config.retrieve_hass_conf.get("days_to_retrieve", 10),
            "model_type": LOAD_FORECAST_MODEL_TYPE,
            "var_model": self._config.power_no_var_loads_id,
            "sklearn_model": "KNeighborsRegressor",
            "num_lags": int(24 / freq),  # should be one day * 30 min
            "split_date_delta": "48h",
            "perform_backtest": True,
        }
        return runtimeparams

    def forecast_model_fit(
        self,
        only_if_file_does_not_exist: bool = False,
        days_to_retrieve: int | None = None,
    ) -> float:
        """Perform a forecast model fit from training data retrieved from Home Assistant."""
        filename = LOAD_FORECAST_MODEL_TYPE + "_mlf.pkl"
        filename_path = self._config._data_folder / filename

        if only_if_file_does_not_exist and filename_path.is_file():
            self._logger.info("Skip model creation")
            return 0

        self._logger.info("Setting up needed data")

        # Treat runtimeparams
        params: str = utils.treat_runtimeparams(
            json.dumps(self.get_ml_runtime_params()),
            json.dumps(self._config.emhass_config),
            self._config.retrieve_hass_conf,
            self._config.optim_conf,
            self._config.plant_conf,
            "forecast-model-fit",
            self._logger,
        )[0]  # type: ignore

        params_dict: dict = json.loads(params)
        # Retrieve data from hass
        if days_to_retrieve is None:
            days_to_retrieve = self._config.retrieve_hass_conf.get("days_to_retrieve", 10)

        days_list = utils.get_days_list(days_to_retrieve)
        var_list = [self._config.power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list)
        df_input_data = self._retrieve_hass.df_final.copy()

        data = copy.deepcopy(df_input_data)
        model_type = params_dict["passed_data"]["model_type"]
        sklearn_model = params_dict["passed_data"]["sklearn_model"]
        num_lags = params_dict["passed_data"]["num_lags"]
        split_date_delta = params_dict["passed_data"]["split_date_delta"]
        perform_backtest = params_dict["passed_data"]["perform_backtest"]

        # The ML forecaster object
        mlf = MLForecaster(
            data,
            model_type,
            self._config.power_no_var_loads_id,
            sklearn_model,
            num_lags,
            self._config.emhass_path_conf,
            self._logger,
        )

        # Fit the ML model
        df_pred = mlf.fit(split_date_delta=split_date_delta, perform_backtest=perform_backtest)
        predictions = df_pred["pred"].dropna()
        test_data = df_pred["test"].dropna()
        r2 = r2_score(test_data, predictions)
        self._logger.info(f"R2 score = {r2}")

        # Save model
        with (self._config._data_folder / filename).open("wb") as outp:
            pickle.dump(mlf, outp, pickle.HIGHEST_PROTOCOL)
        return r2

    def forecast_model_tune(self) -> tuple[pd.DataFrame, MLForecaster]:
        """Tune a forecast model hyperparameters using bayesian optimization."""
        # Load model
        self._logger.info("Tune the forecast model")

        filename = LOAD_FORECAST_MODEL_TYPE + "_mlf.pkl"
        filename_path = self._config._data_folder / filename
        if filename_path.is_file():
            with filename_path.open("rb") as inp:
                mlf = pickle.load(inp)
            # Tune the model
            df_pred_optim = mlf.tune(debug=False)

            # Save model
            with filename_path.open("wb") as outp:
                pickle.dump(mlf, outp, pickle.HIGHEST_PROTOCOL)
            return df_pred_optim, mlf

        self._logger.error(
            "The ML forecaster file was not found, please run a model fit method before this tune method",
        )
        raise MLForecasterTuneError

    def forecast_model_predict(
        self,
        use_last_window: bool = True,
        debug: bool = False,
        mlf: Any | None = None,
    ) -> pd.Series | None:
        """Perform a forecast model predict using a previously trained skforecast model."""
        # Treat runtimeparams
        params: str = ""
        params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
            json.dumps(self.get_ml_runtime_params()),
            json.dumps(self._config.emhass_config),
            self._config.retrieve_hass_conf,
            self._config.optim_conf,
            self._config.plant_conf,
            "forecast-model-fit",
            self._logger,
        )  # type: ignore

        params_dict: dict = json.loads(params)
        # Retrieve data from hass
        days_to_retrieve = params_dict["passed_data"]["days_to_retrieve"]

        days_list = utils.get_days_list(days_to_retrieve)
        var_list = [self._config.power_no_var_loads_id]
        self._retrieve_hass.get_data(days_list, var_list)
        df_input_data = self._retrieve_hass.df_final.copy()

        # Load model
        model_type = "load_forecast"
        filename = model_type + "_mlf.pkl"
        filename_path = self._config._data_folder / filename
        if not debug:
            if filename_path.is_file():
                with filename_path.open("rb") as inp:
                    mlf = pickle.load(inp)
            else:
                self._logger.error(
                    "The ML forecaster file was not found, please run a model fit method before this predict method",
                )
                return None
        # Make predictions
        data_last_window = copy.deepcopy(df_input_data) if use_last_window else None
        if mlf is not None:
            return mlf.predict(data_last_window)
        return None
