from datetime import datetime
from typing import Dict

from model.state.time_state import TimeState
from model.weather_type import WeatherType, HeightType, VectorWeatherType, ScalarWeatherType
from provider import map_weather_data_repository
from rendering.textures.texture import Texture
from service.data_streamer import DataStreamer
from service.weather_data_service import get_scalar_weather_data_checked, get_vector_weather_data_checked, empty
from util.data_texture_util import *
from util.startup import checkpoint


def load_textures_data(time: datetime,
                       scalar: WeatherType, scalar_height: HeightType,
                       vector: VectorWeatherType, vector_height: HeightType) -> Dict[str, np.ndarray]:
    result = dict()
    repo = map_weather_data_repository()

    cloud_height = repo.cloud_type.heights[0] if repo.cloud_type and repo.cloud_type.heights else None
    result["clouds"] = get_scalar_weather_data_checked(repo, time, repo.cloud_type, cloud_height)
    checkpoint()

    vector_field = get_vector_weather_data_checked(repo, time, vector, vector_height)
    result["vector"] = pack_wind_rg(vector_field)
    checkpoint()

    if isinstance(scalar, ScalarWeatherType):
        result["scalar"] = get_scalar_weather_data_checked(repo, time, scalar, scalar_height)
    elif isinstance(scalar, VectorWeatherType):
        if scalar == vector:
            result["scalar"] = wind_speed_from_uv(vector_field)
        else:
            result["scalar"] = wind_speed_from_uv(get_vector_weather_data_checked(repo, time, scalar, scalar_height))
    else:
        result["scalar"] = empty()
    checkpoint()

    return result


class WeatherDataStreamer(DataStreamer):
    def __init__(self,
                 initial_data_time: datetime,
                 initial_scalar: WeatherType, initial_scalar_height: HeightType, initial_vector: VectorWeatherType,
                 initial_vector_height: HeightType, time_state: TimeState):
        super().__init__(time_state)

        self.scalar_type = initial_scalar
        self.scalar_height_type = initial_scalar_height

        self.vector_type = initial_vector
        self.vector_height_type = initial_vector_height

        # Initial synchronous load
        initial_data = load_textures_data(initial_data_time,
                                          initial_scalar, initial_scalar_height,
                                          initial_vector, initial_vector_height)
        self.active_textures = {}
        for texture_id, data in initial_data.items():
            self.active_textures[texture_id] = Texture(
                data, mipmaps=False, repeat_t=False, keep_in_memory=True
            )
            checkpoint()

    def _submit_load(self, time: datetime):
        if time in self.pending or time in self.ready: return

        gen = self.generation
        scalar, scalar_height = self.scalar_type, self.scalar_height_type
        vector, vector_height = self.vector_type, self.vector_height_type

        def task(): return gen, load_textures_data(time, scalar, scalar_height, vector, vector_height)

        self.pending[time] = self.executor.submit(task)

    def apply_data(self):
        textures_data = self.ready.pop(self.current_data_time)
        for id, texture_data in textures_data.items():
            self.active_textures[id].update_data(texture_data)


    def set_data_types(self, new_scalar, new_scalar_height, new_vector, new_vector_height):
        if all([new_scalar == self.scalar_type, new_scalar_height == self.scalar_height_type,
                new_vector == self.vector_type, new_vector_height == self.vector_height_type]):
            return

        self.invalidate()

        self.scalar_type, self.scalar_height_type = new_scalar, new_scalar_height
        self.vector_type, self.vector_height_type = new_vector, new_vector_height

        self._trigger_pipeline()
