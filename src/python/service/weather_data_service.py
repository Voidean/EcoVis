import logging
from datetime import datetime
from typing import Tuple

import numpy as np

from model.weather_type import ScalarWeatherType, HeightType, VectorWeatherType
from repository.weather_data.weather_data_repository import WeatherDataRepository

logger = logging.getLogger(__name__)

def empty():
    return np.full((1, 1, 1), 0, dtype=np.uint8)

def get_scalar_weather_data_checked(repo: WeatherDataRepository,
                                    timestamp: datetime,
                                    datatype: ScalarWeatherType,
                                    height: HeightType | None) -> np.ndarray:
    if timestamp is None or datatype is None:
        return empty()
    else:
        try:
            result = repo.get_scalar_weather_data(timestamp, datatype, height)
            if result is None: return empty()
            return result if isinstance(result, np.ndarray) else empty()
        except Exception as e:
            logger.error("Failed to load scalar weather data", exc_info=True)
            return empty()

def get_vector_weather_data_checked(repo: WeatherDataRepository,
                                    timestamp: datetime,
                                    datatype: VectorWeatherType,
                                    height: HeightType | None) -> Tuple[np.ndarray, np.ndarray]:
    if timestamp is None or datatype is None: return empty(), empty()
    else:
        try:
            result = repo.get_vector_weather_data(timestamp, datatype, height)
            if result is None: return empty(), empty()
            u, v = result
            return (u, v) if isinstance(u, np.ndarray) and isinstance(v, np.ndarray) else (empty(), empty())
        except Exception as e:
            logger.error("Failed to load vector weather data", exc_info=True)
            return empty(), empty()
