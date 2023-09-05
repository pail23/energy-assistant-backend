"""Mqtt connection for energy assistant."""

import copy
from datetime import datetime, timezone
import json
import logging
import pathlib

import numpy as np
import pandas as pd

from app.devices import Location, StateId, StatesRepository
from app.devices.home import Home
from app.devices.homeassistant import HOMEASSISTANT_CHANNEL, Homeassistant
from emhass import utils
from emhass.forecast import forecast
from emhass.optimization import optimization
from emhass.retrieve_hass import retrieve_hass

SENSOR_POWER_NO_VAR_LOADS = "sensor.power_load_no_var_loads"

class EmhassOptimzer:
    """Optimizer based on Emhass."""

    def __init__(self, data_folder: str, config: dict, hass: Homeassistant) -> None:
        """Create an emhass optimizer instance."""
        self._data_folder = data_folder
        self._logger = logging.Logger("EmhassOptimizer")
        self._hass_url: str = hass.url
        if self._hass_url is not None and self._hass_url[-1] != "/":
            self._hass_url = self._hass_url + "/"
        self._hass_token: str = hass.token
        self._location: Location = hass.get_location()

        home_config = config.get("home")
        self._solar_power_id: str | None = None
        if home_config is not None:
            self._solar_power_id = home_config.get("solar_power")
        self._emhass_config = config.get("emhass")


    def update_power_non_var_loads(self, home: Home, state_repository: StatesRepository) -> None:
        """Calculate the power of the non varibale/non controllable loads."""
        power = home.home_consumption_power
        for device in home.devices:
            if device.power_controllable:
                power = power - device.power
        if power < 0:
            power = 0.0
        attributes = {
            "unit_of_measurement": "W",
            "state_class": "measurement",
            "device_class": "power"
        }
        state_repository.set_state(StateId(id=SENSOR_POWER_NO_VAR_LOADS, channel=HOMEASSISTANT_CHANNEL), str(power), attributes)

    def set_input_data_dict(self, costfun: str,
        set_type: str) -> dict:
        """Set up some of the data needed for the different actions.

        :param costfun: The type of cost function to use for optimization problem
        :type costfun: str
        :param set_type: Set the type of setup based on following type of optimization
        :type set_type: str
        :param get_data_from_file: Use data from saved CSV file (useful for debug)
        :type get_data_from_file: bool, optional
        :return: A dictionnary with multiple data used by the action functions
        :rtype: dict

        """
        runtimeparams = None
        if self._hass_url is not None and self._hass_token is not None:
            config_path = pathlib.Path(self._data_folder) / "config_emhass.yaml"
            self._logger.info("Setting up needed data")
            # Parsing yaml
            params = json.dumps(self._emhass_config)
            retrieve_hass_conf, optim_conf, plant_conf = utils.get_yaml_parse(
                pathlib.Path(config_path), False, params=params)
            #Patch variables with Energy Assistant Config
            retrieve_hass_conf['hass_url'] = self._hass_url
            retrieve_hass_conf['long_lived_token'] = self._hass_token
            retrieve_hass_conf["var_PV"] = self._solar_power_id
            retrieve_hass_conf["var_load"] = SENSOR_POWER_NO_VAR_LOADS
            retrieve_hass_conf["var_replace_zero"] = [self._solar_power_id]
            retrieve_hass_conf["var_interp"] = [self._solar_power_id, SENSOR_POWER_NO_VAR_LOADS]

            if self._location is not None:
                retrieve_hass_conf["time_zone"] = self._location.time_zone
                retrieve_hass_conf["lat"] = self._location.latitude
                retrieve_hass_conf["lon"] = self._location.longitude
                retrieve_hass_conf["alt"] = self._location.elevation

            # Treat runtimeparams
            params, retrieve_hass_conf, optim_conf, plant_conf = utils.treat_runtimeparams(
                runtimeparams, params, retrieve_hass_conf,
                optim_conf, plant_conf, set_type, self._logger) # type: ignore
            # Define main objects
            rh = retrieve_hass(self._hass_url, self._hass_token,
                            retrieve_hass_conf['freq'], retrieve_hass_conf['time_zone'],
                            params, self._data_folder, self._logger, get_data_from_file=False)
            fcst = forecast(retrieve_hass_conf, optim_conf, plant_conf,
                            params, self._data_folder, self._logger, get_data_from_file=False)
            opt = optimization(retrieve_hass_conf, optim_conf, plant_conf,
                            fcst.var_load_cost, fcst.var_prod_price,
                            costfun, self._data_folder, self._logger)
            # Perform setup based on type of action
            if set_type == "perfect-optim":
                # Retrieve data from hass
                days_list = utils.get_days_list(retrieve_hass_conf['days_to_retrieve'])
                var_list = [retrieve_hass_conf['var_load'], self._solar_power_id]
                rh.get_data(days_list, var_list,
                            minimal_response=False, significant_changes_only=False)
                rh.prepare_data(retrieve_hass_conf['var_load'], load_negative = retrieve_hass_conf['load_negative'],
                                set_zero_min = retrieve_hass_conf['set_zero_min'],
                                var_replace_zero = retrieve_hass_conf['var_replace_zero'],
                                var_interp = retrieve_hass_conf['var_interp'])
                df_input_data = rh.df_final.copy()
                # What we don't need for this type of action
                P_PV_forecast, P_load_forecast, df_input_data_dayahead = None, None, None
            elif set_type == "dayahead-optim":
                # Get PV and load forecasts
                df_weather = fcst.get_weather_forecast(method=optim_conf['weather_forecast_method'])
                P_PV_forecast = fcst.get_power_from_weather(df_weather)
                P_load_forecast = fcst.get_load_forecast(method=optim_conf['load_forecast_method'])
                df_input_data_dayahead = pd.DataFrame(np.transpose(np.vstack([np.array(P_PV_forecast.values), np.array(P_load_forecast.values)])),
                                                    index=P_PV_forecast.index,
                                                    columns=['P_PV_forecast', 'P_load_forecast'])
                df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)
                params_dayahead: dict = json.loads(params)
                if 'prediction_horizon' in params_dayahead['passed_data'] and params_dayahead['passed_data']['prediction_horizon'] is not None:
                    prediction_horizon = params_dayahead['passed_data']['prediction_horizon']
                    df_input_data_dayahead = copy.deepcopy(df_input_data_dayahead)[df_input_data_dayahead.index[0]:df_input_data_dayahead.index[prediction_horizon-1]]
                # What we don't need for this type of action
                df_input_data, days_list = None, None
            elif set_type == "naive-mpc-optim":
                # Retrieve data from hass
                days_list = utils.get_days_list(1)
                var_list = [retrieve_hass_conf['var_load'], retrieve_hass_conf['var_PV']]
                rh.get_data(days_list, var_list,
                            minimal_response=False, significant_changes_only=False)
                rh.prepare_data(retrieve_hass_conf['var_load'], load_negative = retrieve_hass_conf['load_negative'],
                                set_zero_min = retrieve_hass_conf['set_zero_min'],
                                var_replace_zero = retrieve_hass_conf['var_replace_zero'],
                                var_interp = retrieve_hass_conf['var_interp'])
                df_input_data = rh.df_final.copy()
                # Get PV and load forecasts
                df_weather = fcst.get_weather_forecast(method=optim_conf['weather_forecast_method'])
                P_PV_forecast = fcst.get_power_from_weather(df_weather, set_mix_forecast=True, df_now=df_input_data)
                P_load_forecast = fcst.get_load_forecast(method=optim_conf['load_forecast_method'], set_mix_forecast=True, df_now=df_input_data)
                df_input_data_dayahead = pd.concat([pd.Series(P_PV_forecast, name='P_PV_forecast'), pd.Series(P_load_forecast, name='P_load_forecast')], axis=1)
                df_input_data_dayahead = utils.set_df_index_freq(df_input_data_dayahead)
                #df_input_data_dayahead.columns = ['P_PV_forecast', 'P_load_forecast']
                params_naive_mpc_optim: dict = json.loads(params)
                if 'prediction_horizon' in params_naive_mpc_optim['passed_data'] and params_naive_mpc_optim['passed_data']['prediction_horizon'] is not None:
                    prediction_horizon = params_naive_mpc_optim['passed_data']['prediction_horizon']
                    df_input_data_dayahead = copy.deepcopy(df_input_data_dayahead)[df_input_data_dayahead.index[0]:df_input_data_dayahead.index[prediction_horizon-1]]
            elif set_type == "forecast-model-fit" or set_type == "forecast-model-predict" or set_type == "forecast-model-tune":
                df_input_data_dayahead = None
                P_PV_forecast, P_load_forecast = None, None
                params_forcast: dict = json.loads(params)
                # Retrieve data from hass
                days_to_retrieve = params_forcast['passed_data']['days_to_retrieve']
                var_model = params_forcast['passed_data']['var_model']
                days_list = utils.get_days_list(days_to_retrieve)
                var_list = [var_model]
                rh.get_data(days_list, var_list)
                df_input_data = rh.df_final.copy()
            elif set_type == "publish-data":
                df_input_data, df_input_data_dayahead = None, None
                P_PV_forecast, P_load_forecast = None, None
                days_list = None
            else:
                self._logger.error("The passed action argument and hence the set_type parameter for setup is not valid")
                df_input_data, df_input_data_dayahead = None, None
                P_PV_forecast, P_load_forecast = None, None
                days_list = None

            # The input data dictionnary to return
            input_data_dict = {
                'root': self._data_folder,
                'retrieve_hass_conf': retrieve_hass_conf,
                'rh': rh,
                'opt': opt,
                'fcst': fcst,
                'df_input_data': df_input_data,
                'df_input_data_dayahead': df_input_data_dayahead,
                'P_PV_forecast': P_PV_forecast,
                'P_load_forecast': P_load_forecast,
                'costfun': costfun,
                'params': params,
                'days_list': days_list
            }
            return input_data_dict
        else:
            return {}


    def perfect_forecast_optim(self, input_data_dict: dict,
        save_data_to_file: bool | None = True, debug: bool | None = False) -> pd.DataFrame:
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
        self._logger.info("Performing perfect forecast optimization")
        # Load cost and prod price forecast
        df_input_data = input_data_dict['fcst'].get_load_cost_forecast(
            input_data_dict['df_input_data'],
            method=input_data_dict['fcst'].optim_conf['load_cost_forecast_method'])
        df_input_data = input_data_dict['fcst'].get_prod_price_forecast(
            df_input_data, method=input_data_dict['fcst'].optim_conf['prod_price_forecast_method'])
        opt_res = input_data_dict['opt'].perform_perfect_forecast_optim(df_input_data, input_data_dict['days_list'])
        # Save CSV file for analysis
        if save_data_to_file:
            filename = 'opt_res_perfect_optim_'+input_data_dict['costfun']+'.csv'
        else: # Just save the latest optimization results
            filename = 'opt_res_latest.csv'
        if not debug:
            opt_res.to_csv(pathlib.Path(self._data_folder) / filename, index_label='timestamp')
        return opt_res


    def dayahead_forecast_optim(self, input_data_dict: dict,
        save_data_to_file: bool | None = False, debug: bool | None = False) -> pd.DataFrame:
        """Perform a call to the day-ahead optimization routine.

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
        self._logger.info("Performing day-ahead forecast optimization")
        # Load cost and prod price forecast
        df_input_data_dayahead = input_data_dict['fcst'].get_load_cost_forecast(
            input_data_dict['df_input_data_dayahead'],
            method=input_data_dict['fcst'].optim_conf['load_cost_forecast_method'])
        df_input_data_dayahead = input_data_dict['fcst'].get_prod_price_forecast(
            df_input_data_dayahead,
            method=input_data_dict['fcst'].optim_conf['prod_price_forecast_method'])
        opt_res_dayahead = input_data_dict['opt'].perform_dayahead_forecast_optim(
            df_input_data_dayahead, input_data_dict['P_PV_forecast'], input_data_dict['P_load_forecast'])
        # Save CSV file for publish_data
        if save_data_to_file:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            filename = 'opt_res_dayahead_'+today.strftime("%Y_%m_%d")+'.csv'
        else: # Just save the latest optimization results
            filename = 'opt_res_latest.csv'
        if not debug:
            opt_res_dayahead.to_csv(pathlib.Path(self._data_folder) / filename, index_label='timestamp')
        return opt_res_dayahead
