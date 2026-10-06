from dataclasses import dataclass


@dataclass(frozen=True)
class HeightType:
    identifier: str
    display_name: str


@dataclass(frozen=True)
class WeatherType:
    display_name: str
    heights: list[HeightType] | None
    data_max: float = 1
    unit: str = ""


@dataclass(frozen=True)
class ScalarWeatherType(WeatherType):
    data_min: float = 0
    identifier: str = ""


@dataclass(frozen=True)
class VectorWeatherType(WeatherType):
    identifier_u: str = ""
    identifier_v: str = ""

SYNC_SCALAR = ScalarWeatherType(identifier="SYNC_SCALAR", display_name="Sync with Particles", heights=None)