from dataclasses import dataclass
from datetime import datetime

from model.geo_pos import GeoPos
from repository.weather_data.point_weather_data_repository import HourlyType, DailyType


@dataclass(frozen=True)
class PowerPlotRequest:
    plants: list[int]
    start_time: datetime
    end_time: datetime
    years_prior: int


@dataclass(frozen=True)
class WeatherPlotRequest:
    geo_pos: GeoPos
    start_time: datetime
    end_time: datetime
    years_prior: int
    data_type: HourlyType | DailyType
    tilt: int
    azimuth: int | tuple[int, ...]


GraphPlotRequest = PowerPlotRequest | WeatherPlotRequest


@dataclass(frozen=True)
class WindroseRequest:
    location: GeoPos
    start_date: datetime
    end_date: datetime
