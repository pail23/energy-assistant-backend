"""Use cases for devices."""

from datetime import datetime
import os

import pandas as pd

from app.settings import settings

from .schema import ForecastSchema


class ReadForecast:
    """Read the forecast."""

    async def execute(self) -> ForecastSchema:
        """Execute the read all devices use case."""
        today = datetime.now().strftime("%Y_%m_%d")
        df = pd.read_csv(os.path.join(settings.DATA_FOLDER, f"opt_res_dayahead_{today}.csv"))
        time = df["timestamp"].to_list()
        pv = df["P_PV"].to_list()
        load = df["P_Load"].to_list()
        return ForecastSchema(time=time,series={"pv": pv, "load": load})
