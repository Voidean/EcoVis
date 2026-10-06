from datetime import datetime, timedelta, timezone
from typing import Tuple

import numpy as np
from herbie import Herbie

from model.weather_type import ScalarWeatherType, HeightType
from model.herbie_types import HerbieScalarWeatherType, HerbieVectorWeatherType, HERBIE_SCALARS, HERBIE_VECTORS
from repository.weather_data.weather_data_repository import WeatherDataRepository
from util.time_util import TIME_FORMAT, TIME_FORMAT_DISPLAY, get_datatime_delta_to_now_h

HERBIE_TIME_INCREMENT = timedelta(hours=6)


class HerbieWeatherDataRepository(WeatherDataRepository):
    @property
    def initial_time(self) -> datetime:
        return datetime.strptime("20260101_12", TIME_FORMAT).replace(tzinfo=timezone.utc)

    @property
    def time_increment(self) -> timedelta:
        return HERBIE_TIME_INCREMENT

    @property
    def scalar_data_types(self) -> list[HerbieScalarWeatherType]:
        return HERBIE_SCALARS

    @property
    def vector_data_types(self) -> list[HerbieVectorWeatherType]:
        return HERBIE_VECTORS

    @property
    def cloud_type(self) -> ScalarWeatherType | None:
        return HERBIE_SCALARS[1]

    def get_scalar_weather_data(self, timestamp: datetime, data_type: HerbieScalarWeatherType,
                                height: HeightType = None) -> None | np.ndarray:
        """Loads scalar weather data from Herbie API map-tiles endpoint.
            Params:
                timestamp (datetime): timestamp of data
                datatype (ScalarWeatherType): data type to load
                height (HeightType): optional height for data type
            Returns:
                The weather data as a np.ndarray representing a texture
        """
        diff = get_datatime_delta_to_now_h(timestamp, HERBIE_TIME_INCREMENT)
        timestamp -= timedelta(hours=diff)
        return load_grib_data(data_time=timestamp,
                              request_name=data_type.identifier,
                              return_names=data_type.return_names,
                              height=height.identifier if height else None,
                              data_min=data_type.data_min,
                              data_max=data_type.data_max,
                              fxx=diff)

    def get_vector_weather_data(self, timestamp: datetime, data_type: HerbieVectorWeatherType,
                                height: HeightType = None) -> Tuple[np.ndarray, np.ndarray] | None:
        """Loads vector weather data from Herbie map-tiles API endpoint.
            Params:
                timestamp (datetime): timestamp of data
                datatype (VectorWeatherType): data type to load
                height (HeightType): optional height for data type
            Returns:
                The weather data as a tuple of np.ndarray representing u- and v-textures
        """
        diff = get_datatime_delta_to_now_h(timestamp, HERBIE_TIME_INCREMENT)
        timestamp -= timedelta(hours=diff)
        return (load_grib_data(data_time=timestamp,
                               request_name=data_type.identifier_u,
                               return_names=data_type.return_names,
                               height=height.identifier if height else None,
                               data_min=0.0,
                               data_max=data_type.data_max,
                               fxx=diff),
                load_grib_data(data_time=timestamp,
                               request_name=data_type.identifier_v,
                               return_names=data_type.return_names,
                               height=height.identifier if height else None,
                               data_min=0.0,
                               data_max=data_type.data_max,
                               fxx=diff))


def load_grib_data(
        data_time: datetime,
        request_name: str,
        return_names: list[str],
        height: str = None,
        model: str = "gfs",
        fxx: int = 0,
        data_min=0.0, data_max=100.0) -> np.ndarray:
    """Helper method to get data from Herbie map-tiles API endpoint.
        Params:
            data_time (datetime): timestamp of data
            request_name (str): request name for data type
            return_names (list[str]): variable names for data type in API response body
            height (HeightType): optional height for data type
            model (str): API model to use for request
            data_min (int): minimum value for data type normalization
            data_max (int): maximum value for data type normalization
        Returns:
            Loaded Image data as numpy array
    """
    request = f":{request_name}{f':{height}' if height is not None else ''}"

    h = Herbie(date=f"{data_time.strftime(TIME_FORMAT_DISPLAY)}", model=model, fxx=fxx)

    data = h.xarray(request)
    for var_name in return_names:
        try:
            data = data[0][var_name].values.astype(np.float32)
            break
        except (KeyError, TypeError, IndexError):
            try:
                data = data[var_name].values.astype(np.float32)
                break
            except (KeyError, TypeError, IndexError):
                continue

    data = np.nan_to_num(data, nan=0.0)  # Replace NaNs
    data = (data - data_min) / (data_max - data_min)  # Normalize
    height, width = data.shape
    data = np.roll(data, shift=width // 2, axis=1)  # Rotate east to west
    return data
