from pyglm import glm

from model.gradient import get_default_gradient
from model.projection import Projection
from provider import map_weather_data_repository, power_metadata_repository
from util.config import config


POWER_PLANT_COLOR_PALETTE = (
    glm.vec4(0.20, 0.75, 1.00, 1.0),
    glm.vec4(0.20, 0.55, 0.95, 1.0),
    glm.vec4(1.00, 0.75, 0.10, 1.0),
    glm.vec4(0.35, 0.80, 0.30, 1.0),
    glm.vec4(0.90, 0.35, 0.65, 1.0),
    glm.vec4(0.75, 0.45, 0.95, 1.0),
    glm.vec4(0.95, 0.45, 0.20, 1.0),
)


class RenderState:
    def __init__(self):
        self.changed = False

        self.render_clouds = True
        self.render_atmosphere = True
        self.render_shadows = True

        self.projection = Projection.GLOBE
        self.vertical_scale = 1.0

        self.render_data = False
        self.gradient = get_default_gradient()
        self.scale_start = 0.0
        self.scale_end = 1.0

        self.simulate_wind = False
        self.particle_speed = 1.0
        self.num_particles = 100_000
        self.particle_resolution = 256

        plant_types = power_metadata_repository().plant_types
        self.render_power_plants = {plant_type: False for plant_type in plant_types}
        self.power_plant_colors = {
            plant_type: POWER_PLANT_COLOR_PALETTE[index % len(POWER_PLANT_COLOR_PALETTE)]
            for index, plant_type in enumerate(plant_types)
        }
        self.power_plant_point_size = 32.0
        # Keep the previous behaviour as the default; the settings can now
        # disable either representation independently.
        self.render_power_plant_points = True
        self.render_power_plant_models = True
        self.model_scale = config.graphics.power_plant_scale

        self.render_power_grid = False
        self.power_grid_color = glm.vec4(0.0, 1.0, 0.0, 1.0)

        self.render_coastlines = False
        self.render_borders = False
        self.border_color = glm.vec4(1.0)

        self.camera_reset = False
        self.scalar_data_type = map_weather_data_repository().scalar_data_types[0]
        self.scalar_height_type = self.scalar_data_type.heights[0] if self.scalar_data_type.heights else None

        self.vector_data_type = map_weather_data_repository().vector_data_types[0]
        self.vector_height_type = self.vector_data_type.heights[0] if self.vector_data_type.heights else None

    def should_render_clouds(self):
        return self.render_clouds and not self.render_data

    def should_render_atmosphere(self):
        return self.render_atmosphere and not self.render_data


render_state: RenderState = RenderState()
