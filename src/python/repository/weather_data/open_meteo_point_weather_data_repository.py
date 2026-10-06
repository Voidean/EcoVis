from datetime import datetime, timedelta
from typing import Optional

import openmeteo_requests
import numpy as np
import requests_cache
from retry_requests import retry

from model.geo_pos import GeoPos
from repository.weather_data.point_weather_data_repository import (
    Azimuth,
    DailyType,
    HourlyType,
    PointWeatherData,
    PointWeatherDataRepository,
)
from util.paths import CACHE


class OpenMeteoApi(PointWeatherDataRepository):
    def __init__(self):
        cache_session = requests_cache.CachedSession(str(CACHE / "cache.sqlite"), expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.client = openmeteo_requests.Client(session=retry_session)

        self.forecast_url = "https://api.open-meteo.com/v1/forecast"
        self.historical_url = "https://archive-api.open-meteo.com/v1/archive"

    def fetch_data(self, lat: float, lon: float,
                   data_type: DailyType | HourlyType,
                   start_date: datetime, end_time: datetime,
                   tilt: float = None,
                   azimuth: Azimuth = None) -> Optional[PointWeatherData]:
        azimuths = azimuth if isinstance(azimuth, tuple) else (azimuth,)
        results = [self._fetch_data(
            lat, lon, data_type, start_date, end_time, tilt, panel_azimuth
        ) for panel_azimuth in azimuths]
        if any(result is None for result in results):
            return None
        if len(results) == 1:
            return results[0]

        timestamps = results[0].timestamps
        aligned_values = [results[0].values]
        for result in results[1:]:
            timestamps, left_indices, right_indices = np.intersect1d(
                timestamps,
                result.timestamps,
                return_indices=True,
            )
            aligned_values = [values[left_indices] for values in aligned_values]
            aligned_values.append(result.values[right_indices])
        values = np.mean(np.stack(aligned_values), axis=0)
        first_result = results[0]
        return PointWeatherData(
            timestamps=timestamps,
            values=values,
            position=first_result.position,
            model_name=first_result.model_name,
            is_forecast=first_result.is_forecast,
        )

    def _fetch_data(self, lat: float, lon: float,
                    data_type: DailyType | HourlyType,
                    start_date: datetime, end_time: datetime,
                    tilt: float = None,
                    azimuth: float = None) -> Optional[PointWeatherData]:
        is_wind_power_density = data_type == HourlyType.WIND_POWER_DENSITY_100M
        params = {
            "latitude": lat,
            "longitude": lon,
            "models": "ecmwf_ifs",
            "wind_speed_unit": "ms",
            "start_date": start_date.date().isoformat(),
            "end_date": end_time.date().isoformat(),
        }
        if is_wind_power_density:
            params["hourly"] = ["surface_pressure", "wind_speed_100m", "temperature_2m"]
        elif isinstance(data_type, DailyType):
            params["daily"] = data_type.api_name
        else:
            params["hourly"] = data_type.api_name
            if data_type == HourlyType.GLOBAL_TILTED_IRRADIANCE and tilt is not None and azimuth is not None:
                params["tilt"] = tilt
                params["azimuth"] = azimuth

        response_url = self.historical_url
        try:
            response = self.client.weather_api(self.historical_url, params=params)[0]
        except Exception:
            try:
                response_url = self.forecast_url
                response = self.client.weather_api(self.forecast_url, params=params)[0]
            except Exception:
                return None

        position = GeoPos.from_degrees(response.Longitude(), response.Latitude())
        if is_wind_power_density:
            hourly = response.Hourly()
            pressure = hourly.Variables(0).ValuesAsNumpy() * 100
            wind_speed = hourly.Variables(1).ValuesAsNumpy()
            temperature = hourly.Variables(2).ValuesAsNumpy() + 273.15
            values_array = 0.5 * pressure / (287.058 * temperature) * wind_speed ** 3 / 1000
            timestamps = np.array(
                [start_date + timedelta(hours=i) for i in range(values_array.size)],
                dtype=object,
            )
            values = np.asarray(values_array.flatten(), dtype=np.float64)
        else:
            values_array = (response.Daily() if isinstance(data_type, DailyType)
                            else response.Hourly()).Variables(0).ValuesAsNumpy()
            time_step = timedelta(days=1) if isinstance(data_type, DailyType) else timedelta(hours=1)
            time_start = start_date.replace(hour=12) if isinstance(data_type, DailyType) else start_date
            timestamps = np.array(
                [time_start + time_step * i for i in range(values_array.size)],
                dtype=object,
            )
            values = np.asarray(values_array.flatten(), dtype=np.float64)
        return PointWeatherData(
            timestamps=timestamps,
            values=values,
            position=position,
            model_name=self._model_name(response),
            is_forecast=response_url == self.forecast_url,
        )

    @staticmethod
    def _model_name(response) -> str | None:
        model = getattr(response, "Model", None)
        if model is None:
            return None
        try:
            model_value = model()
            from openmeteo_sdk import Model
            for name, value in vars(Model.Model).items():
                if value == model_value:
                    return name.replace("_", " ").upper()
        except (AttributeError, TypeError, ImportError):
            return None
        return None
