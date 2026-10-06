import math

import numpy as np
from pyglm import glm

from model.weather_type import ScalarWeatherType, WeatherType
from provider import map_weather_data_repository
from util.coordinate_conversion import geo_pos_to_uv
from util.data_texture_util import bilinear_sample, scale, unscale

min_lon, max_lon = map_weather_data_repository().geographic_range_longitude
min_lat, max_lat = map_weather_data_repository().geographic_range_latitude

if min_lon != -180 or max_lon != 180 or min_lat != -90 or max_lat != 90:
    if min_lon < -180 or min_lat == max_lat or max_lon > 180: raise ValueError("Invalid longitude range")
    if min_lat < -90 or min_lat >= max_lat or max_lat > 90: raise ValueError("Invalid latitude range")

    use_data_range = True
    data_range_start = geo_pos_to_uv(math.radians(min_lon), math.radians(min_lat))
    data_range_end = geo_pos_to_uv(math.radians(max_lon), math.radians(max_lat))
else:
    use_data_range = False
    data_range_start = glm.vec2(0, 0) # x = longitude min, y = latitude min
    data_range_end = glm.vec2(1, 1)   # x = longitude max, y = latitude max


def get_mapped_uv(uv: glm.vec2) -> glm.vec2 | None:
    if not use_data_range: return uv

    u = uv.x - math.floor(uv.x)
    v = uv.y

    u_scaled = -1.0

    if data_range_start.x <= data_range_end.x:
        # Standard Case
        u_scaled = scale(u, data_range_start.x, data_range_end.x)
    else:
        # Wrap-around Case
        span = (1.0 - data_range_start.x) + data_range_end.x
        if u >= data_range_start.x:
            u_scaled = (u - data_range_start.x) / span
        elif u <= data_range_end.x:
            u_scaled = (1.0 - data_range_start.x + u) / span

    v_scaled = scale(v, data_range_start.y, data_range_end.y)

    return glm.vec2(u_scaled, v_scaled) if (0.0 <= u_scaled <= 1.0 and 0.0 <= v_scaled <= 1.0) else None


def get_data_read_out(data: np.ndarray, uv: glm.vec2, weather: WeatherType) -> str:
    uv = get_mapped_uv(uv)
    if uv is None: return "No data"

    data_value = bilinear_sample(data, uv)
    data_min = weather.data_min if isinstance(weather, ScalarWeatherType) else 0
    data_max = weather.data_max if isinstance(weather, ScalarWeatherType) else math.sqrt(2) * weather.data_max

    return f"{unscale(data_value, data_min, data_max):.2f} {weather.unit}\n"
