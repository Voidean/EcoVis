from dataclasses import dataclass
from enum import StrEnum


class ViewId(StrEnum):
    MAIN_MENU_BAR = "main_menu_bar"
    HELP = "help"
    LOADING = "loading"
    FPS = "fps"
    COMPASS = "compass"
    TIME_CONTROL = "time_control"
    DEBUG = "debug"
    CONFIG = "config"
    DATA = "data"
    MAP_WEATHER_CONTROL = "map_weather_control"


@dataclass(frozen=True)
class ViewMetadata:
    id: ViewId
    title: str
