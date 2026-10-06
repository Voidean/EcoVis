from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple

import numpy as np

from model.weather_type import WeatherType, HeightType, ScalarWeatherType, VectorWeatherType


class WeatherDataRepository(ABC):
    @property
    @abstractmethod
    def scalar_data_types(self) -> list[ScalarWeatherType]:
        """Define supported scalar types here."""
        pass

    @property
    @abstractmethod
    def vector_data_types(self) -> list[VectorWeatherType]:
        """Define supported vector types here."""
        pass

    @property
    def data_types(self) -> list[WeatherType]:
        """Returns the combined list of all weather types."""
        return self.scalar_data_types + self.vector_data_types

    @property
    def cloud_type(self) -> ScalarWeatherType | None:
        """Define cloud type here.
        This is displayed if not in the data rendering mode.
        Defaults to None, can be overridden if needed.
        """
        return None

    @property
    def data_times(self) -> list[datetime] | None:
        """Optionally define supported data times here."""
        return None

    @property
    @abstractmethod
    def initial_time(self) -> datetime:
        """Define initial data time here. This is the timestamp that will be selected on startup."""
        pass

    @property
    @abstractmethod
    def time_increment(self) -> timedelta:
       pass

    @property
    def geographic_range_longitude(self) -> tuple[float, float]:
        """Define longitude range here in degrees. If first value is greater than the second, range will wrap east to west instead.
        Data will be interpreted to be inside this range.
        Values need to be between -180 and 180.
        """
        return -180, 180

    @property
    def geographic_range_latitude(self) -> tuple[float, float]:
        """Define latitude range here in degrees. First value is min latitude, second value is max latitude and must be greater.
        Data will be interpreted to be inside this range.
        Values need to be between -90 and 90.
        """
        return -90, 90

    @abstractmethod
    def get_scalar_weather_data(self, timestamp: datetime, datatype: ScalarWeatherType, height: HeightType = None) -> None | np.ndarray:
        """Loads the weather data for a given time
        Args:
            timestamp: Time of the measurement
            datatype: Type of weather data e.g. temperature
            height: Height of the measurement (e.g. 1000hPa)
        Returns:
            The weather data as a two-dimensional np.ndarray representing a texture
            - Allowed data types are: uint8, uint16, float16, float32
            - height, width = result.shape must match for correct orientation (column-major)
            - height represents latitude range and width represents longitude range as specified with the given properties
            -> longitude goes from a range of -180 deg to +180 deg (west to east)
            -> latitude goes from +90 deg to -90 deg (north to south)

            Data must be normalised with the following encoding:
            -> scalar floats:
                0.0 is data_min,
                1.0 is data_max
            -> scalar uint8 (similar for the range of uint16):
                0 is data_min,
                255 is data_max,
        """
        pass

    @abstractmethod
    def get_vector_weather_data(self, timestamp: datetime, datatype: VectorWeatherType, height: HeightType = None) -> Tuple[np.ndarray, np.ndarray] | None:
        """Loads the weather data for a given time
        Args:
            timestamp: Time of the measurement
            datatype: Type of weather data e.g. wind
            height: Height of the measurement (e.g. 1000hPa)
        Returns:
            The weather data as a tuple of two-dimensional np.ndarrays representing u- and v-textures
            - Allowed data types are: uint8, uint16, float16, float32
            - height, width = result.shape must match for correct orientation (column-major)
            - height represents latitude range and width represents longitude range as specified with the given properties
            -> longitude goes from a range of -180 deg to +180 deg (west to east)
            -> latitude goes from +90 deg to -90 deg (north to south)
            - vector u and v components must match in size and data type

            Data must be normalised with the following encoding:
            -> vector floats:
                -1.0 is -data_max,
                0.0 corresponds to a vector of 0.0,
                1.0 is data_max
            -> vector uint8 (similar for the range of uint16):
                0 is -data_max,
                127 (midpoint) is 0,
                255 is data_max
        """
        pass
