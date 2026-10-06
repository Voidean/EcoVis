import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import json
import numpy as np
from PIL import Image

from model.weather_type import ScalarWeatherType, HeightType, VectorWeatherType
from rendering.textures.texture import load_image_data
from repository.weather_data.weather_data_repository import WeatherDataRepository
from util.paths import WEATHER
from util.time_util import TIME_FORMAT, DEFAULT_DATATIME_DELTA


def load_weather_types():
    """Loads valid weather types from JSON"""
    with open(WEATHER / "weather_config.json", 'r', encoding='utf-8') as f:
        data = json.load(f)

    def parse_heights(h_list):
        if not h_list:
            return None
        return [HeightType(**h) for h in h_list]

    scalars = [
        ScalarWeatherType(
            display_name=s["display_name"],
            identifier=s["identifier"],
            heights=parse_heights(s.get("heights")),
            data_min=s.get("data_min", 0),
            data_max=s.get("data_max", 1),
            unit=s.get("unit")
        ) for s in data.get("scalars", [])
    ]

    vectors = [
        VectorWeatherType(
            display_name=v["display_name"],
            identifier_u=v["identifier_u"],
            identifier_v=v["identifier_v"],
            heights=parse_heights(v.get("heights")),
            data_max=v.get("data_max", 1),
            unit=v.get("unit")
        ) for v in data.get("vectors", [])
    ]

    return scalars, vectors

def load_data_times():
    with open(WEATHER / "weather_config.json", 'r', encoding='utf-8') as f:
        data = json.load(f)

    time = data.get("start_time")
    end_time = data.get("end_time")
    default_time = data.get("default_time")
    time_delta = data.get("time_increment_h", DEFAULT_DATATIME_DELTA)
    result = []
    if time and end_time and default_time:
        time = datetime.strptime(time, TIME_FORMAT).replace(tzinfo=timezone.utc)
        end_time = datetime.strptime(end_time, TIME_FORMAT).replace(tzinfo=timezone.utc)
        default_time = datetime.strptime(default_time, TIME_FORMAT).replace(tzinfo=timezone.utc)
        time_delta = timedelta(hours=time_delta)
        while time <= end_time:
            result.append(time)
            time += time_delta
        return result, default_time, time_delta
    else:
        # Use folder names
        for name in os.listdir(WEATHER):
            if os.path.isdir(os.path.join(WEATHER, name)):
                try:
                    dt = datetime.strptime(name, TIME_FORMAT).replace(tzinfo=timezone.utc)
                    result.append(dt)
                except ValueError:
                    continue
        return result, result[0], time_delta


class FileWeatherDataRepository(WeatherDataRepository):
    """WeatherDataRepository implementation that reads weather data from image files."""

    SCALARS, VECTORS = load_weather_types()
    DATA_TIMES, INITIAL_TIME, TIME_INCREMENT = load_data_times()


    @property
    def scalar_data_types(self) -> list[ScalarWeatherType]:
        return self.SCALARS

    @property
    def vector_data_types(self) -> list[VectorWeatherType]:
        return self.VECTORS

    @property
    def data_times(self) -> list[datetime]:
        return self.DATA_TIMES

    @property
    def initial_time(self) -> datetime:
        return self.INITIAL_TIME

    @property
    def time_increment(self) -> int:
        return self.TIME_INCREMENT

    @property
    def cloud_type(self) -> ScalarWeatherType | None:
        return self.SCALARS[4]

    def get_data(self, data_time: datetime, data_type_id: str, height_type_id: str | None):
        """Helper method to get data from local image files.
            Params:
                data_time (datetime): timestamp of data
                data_type_id (str): name of data type
                height_type_id (str): name of height type
            Returns:
                The weather data as a np.ndarray representing a texture
        """
        folder_name = data_time.strftime(TIME_FORMAT)
        height_type_id = "_" + height_type_id if height_type_id else ""
        data_path = WEATHER / folder_name / f"{data_type_id}{height_type_id}.png"

        if os.path.exists(data_path): return load_image_data(Image.open(data_path))
        else: return None

    def get_scalar_weather_data(self, timestamp: datetime, datatype: ScalarWeatherType, height: HeightType = None) -> None | np.ndarray:
        """Loads scalar weather data from image files.
            Params:
                timestamp (datetime): timestamp of data
                datatype (ScalarWeatherType): data type to load
                height (HeightType): optional height for data type
            Returns:
                The weather data as a np.ndarray representing a texture
        """
        return self.get_data(timestamp, datatype.identifier, height.identifier if height else None)

    def get_vector_weather_data(self, timestamp: datetime, datatype: VectorWeatherType, height: HeightType = None) -> Tuple[np.ndarray, np.ndarray] | None:
        """Loads vector weather data from image files.
            Params:
                timestamp (datetime): timestamp of data
                datatype (VectorWeatherType): data type to load
                height (HeightType): optional height for data type
            Returns:
                The weather data as a tuple of np.ndarray representing u- and v-textures
        """
        return (self.get_data(timestamp, datatype.identifier_u, height.identifier if height else None),
                self.get_data(timestamp, datatype.identifier_v, height.identifier if height else None))
