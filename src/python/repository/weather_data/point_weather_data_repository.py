from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, EnumType
from typing import Union, Optional

import numpy as np

from model.geo_pos import GeoPos

Azimuth = float | tuple[int, ...]


@dataclass(frozen=True)
class PointWeatherData:
    """NumPy weather series together with the provider's resolved grid position."""

    timestamps: np.ndarray
    values: np.ndarray
    position: GeoPos
    model_name: str | None = None
    is_forecast: bool = False


class NamedEnumMeta(EnumType):
    def __str__(cls):
        enum_class_display_names = {
            "DailyType": "Daily",
            "HourlyType": "Hourly"
        }
        return enum_class_display_names.get(cls.__name__, cls.__name__)


class DailyType(Enum, metaclass=NamedEnumMeta):
    # --- Temperature ---
    TEMPERATURE_MEAN = ("temperature_2m_mean", "Mean Temperature (2m)", "°C")
    TEMPERATURE_MAX = ("temperature_2m_max", "Max Temperature (2m)", "°C")
    TEMPERATURE_MIN = ("temperature_2m_min", "Min Temperature (2m)", "°C")

    APPARENT_TEMPERATURE_MEAN = ("apparent_temperature_mean", "Mean Apparent Temperature", "°C")
    APPARENT_TEMPERATURE_MAX = ("apparent_temperature_max", "Max Apparent Temperature", "°C")
    APPARENT_TEMPERATURE_MIN = ("apparent_temperature_min", "Min Apparent Temperature", "°C")

    RELATIVE_HUMIDITY_MEAN = ("relative_humidity_2m_mean", "Mean Relative Humidity", "%")
    RELATIVE_HUMIDITY_MAX = ("relative_humidity_2m_max", "Max Relative Humidity", "%")
    RELATIVE_HUMIDITY_MIN = ("relative_humidity_2m_min", "Min Relative Humidity", "%")

    # --- Wind ---
    WIND_SPEED_MEAN = ("wind_speed_10m_mean", "Mean Wind Speed", "m/s")
    WIND_SPEED_MAX = ("wind_speed_10m_max", "Max Wind Speed (10m)", "m/s")
    WIND_GUSTS_MEAN = ("wind_gusts_10m_mean", "Mean Wind Gusts", "m/s")
    WIND_GUSTS_MAX = ("wind_gusts_10m_max", "Max Wind Gusts (10m)", "m/s")
    WIND_DIRECTION_DOMINANT = ("wind_direction_10m_dominant", "Dominant Wind Direction (10m)", "°")

    # --- Solar & Radiation ---
    DAYLIGHT_DURATION = ("daylight_duration", "Daylight Duration", "s")
    SUNSHINE_DURATION = ("sunshine_duration", "Sunshine Duration", "s")
    SHORTWAVE_RADIATION_SUM = ("shortwave_radiation_sum", "Shortwave Radiation (Sum)", "MJ/m²")

    # --- Water & Precipitation ---
    PRECIPITATION_SUM = ("precipitation_sum", "Precipitation (Sum)", "mm")
    EVAPOTRANSPIRATION = ("et0_fao_evapotranspiration", "Evapotranspiration (ET0 FAO)", "mm")

    def __init__(self, api_name: str, display_name: str, unit = None):
        self.api_name = api_name
        self.display_name = display_name
        self.unit = unit


class HourlyType(Enum, metaclass=NamedEnumMeta):
    # --- Temperature & Humidity ---
    TEMPERATURE = ("temperature_2m", "Temperature (2m)", "°C")
    APPARENT_TEMPERATURE = ("apparent_temperature", "Apparent Temperature", "°C")
    DEW_POINT = ("dew_point_2m", "Dew Point (2m)", "°C")
    RELATIVE_HUMIDITY = ("relative_humidity_2m", "Relative Humidity (2m)", "%")

    SURFACE_PRESSURE = ("surface_pressure", "Surface Pressure", "hPa")

    # --- Wind ---
    WIND_SPEED_10M = ("wind_speed_10m", "Wind Speed (10m)", "m/s")
    WIND_SPEED_100M = ("wind_speed_100m", "Wind Speed (100m)", "m/s")
    WIND_GUSTS_10M = ("wind_gusts_10m", "Wind Gusts (10m)", "m/s")
    WIND_DIRECTION_10M = ("wind_direction_10m", "Wind Direction (10m)", "°")
    WIND_DIRECTION_100M = ("wind_direction_100m", "Wind Direction (100m)", "°")
    WIND_POWER_DENSITY_100M = ((WIND_SPEED_100M, SURFACE_PRESSURE), "Wind Power Density", "kW/m²")

    # --- Precipitation ---
    PRECIPITATION = ("precipitation", "Precipitation", "mm")
    RAIN = ("rain", "Rain", "mm")

    # --- Solar ---
    GLOBAL_TILTED_IRRADIANCE = ("global_tilted_irradiance", "Global Tilted Irradiance", "W/m²")

    def __init__(self, api_name: str, display_name: str, unit = None):
        self.api_name = api_name
        self.display_name = display_name
        self.unit = unit

class PointWeatherDataRepository(ABC):
    @abstractmethod
    def fetch_data(self, lat: float, lon: float,
                   data_type: Union[DailyType, HourlyType],
                   start_date: datetime, end_time: datetime,
                   tilt: float = None,
                   azimuth: Azimuth = None) -> Optional[PointWeatherData]:
        """Fetch values together with the provider-resolved position."""
        raise NotImplementedError
