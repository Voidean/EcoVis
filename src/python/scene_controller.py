from pyglm import glm

from input import Input
from model.projection import Projection
from model.state.render_state import render_state as rs
from model.state.time_state import time_state as ts
from model.state.debug_state import debug_state as ds
from model.weather_type import SYNC_SCALAR
from provider import power_metadata_repository, map_weather_data_repository
from rendering.particles import Particles
from rendering.scene.scene import Scene
from rendering.textures.frame_buffer import FrameBuffer
from repository.astronomy_repository import calculate_sun_direction, calculate_moon_direction, calculate_sky_rotation
from repository.globe_borders_repository import BORDER_KEYS
from service.camera_flight import CameraFlight
from service.camera_movement import CameraMovement
from service.map_tiles.level_of_detail import LevelOfDetail
from service.weather_data_streamer import WeatherDataStreamer
from util.config import config
from util.coordinate_constants import GLOBE_RADIUS
from util.data_reading_util import data_range_start, data_range_end, use_data_range
from util.startup import checkpoint


class SceneController:
    def __init__(
        self,
        scene: Scene,
        frame_buffer: FrameBuffer,
        input: Input,
        camera_flight: CameraFlight,
    ):
        self.scene = scene
        self.frame_buffer = frame_buffer
        self.input = input
        self.config_revision = config.revision
        checkpoint()

        self.camera_movement = CameraMovement(input)
        self.camera_flight = camera_flight
        checkpoint()

        self.weather_data_streamer = WeatherDataStreamer(
            initial_data_time=map_weather_data_repository().initial_time,
            initial_scalar=rs.scalar_data_type,
            initial_scalar_height=rs.scalar_height_type,
            initial_vector=rs.vector_data_type,
            initial_vector_height=rs.vector_height_type,
            time_state=ts,
        )
        checkpoint()
        self.particles = Particles(
            num_particles=rs.num_particles,
            frame_buffer_resolution=rs.particle_resolution,
            tiles_ssbo=self.scene.drawables["map_tiles"].instance_ssbo,
        )
        checkpoint()

        self.level_of_detail = LevelOfDetail()
        checkpoint()

        self.map_tiles = self.scene.drawables["map_tiles"]
        self.north_pole = self.scene.drawables["north_polar_cap"]
        self.south_pole = self.scene.drawables["south_polar_cap"]
        self.clouds = self.scene.drawables["clouds"]
        self.sun = self.scene.drawables["sun"]
        self.moon = self.scene.drawables["moon"]
        self.sky = self.scene.drawables["sky"]

        self.atmosphere_shader = self.scene.screen_space_shaders["atmosphere"]

        self.set_geographic_range()
        checkpoint()
        self.update_celestial_objects(ts.current_time)
        checkpoint()
        self.link_textures()
        checkpoint()
        self.apply_graphics_config()
        checkpoint()
        self.apply_render_settings()
        checkpoint()
        self.apply_debug_settings()
        checkpoint()

    def set_geographic_range(self):
        globe_shader = self.scene.shaders["globe"]
        globe_shader.use()
        globe_shader.set_bool("useDataRange", use_data_range)
        globe_shader.set_vec2("dataStart", data_range_start)
        globe_shader.set_vec2("dataEnd", data_range_end)

    def link_textures(self):
        self.map_tiles.mesh.textures["particleTexture"] = self.particles.frame_buffer.color_tex
        self.north_pole.mesh.textures["particleTexture"] = self.particles.polar_frame_buffer.color_tex
        self.south_pole.mesh.textures["particleTexture"] = self.particles.polar_frame_buffer.color_tex

        for channel, texture_array in self.level_of_detail.cache.arrays.items():
            self.map_tiles.mesh.textures[channel.identifier] = texture_array

        weather_textures = self.weather_data_streamer.active_textures

        for drawable in [self.map_tiles, self.north_pole, self.south_pole]:
            drawable.mesh.textures["dataMap"] = weather_textures["scalar"]
        self.particles.particle_texture = weather_textures["vector"]
        self.scene.drawables["clouds"].mesh.textures["alpha"] = weather_textures["clouds"]

    @property
    def weather_data_textures(self):
        return self.weather_data_streamer.active_textures

    def update(self, delta_time):
        if self.config_revision != config.revision:
            self.apply_graphics_config()
            self.config_revision = config.revision

        if self.camera_flight.update(delta_time):
            self.input.drag_delta = 0, 0
            self.input.scroll_delta = 0
        else:
            self.camera_movement.update_movement(self.scene.camera, delta_time, rs.projection)

        ts.advance(delta_time)

        if ts.changed:
            self.update_celestial_objects(ts.current_time)
            self.weather_data_streamer.set_time(ts.current_data_time)
            ts.changed = False

        if rs.changed:
            self.apply_render_settings()
            rs.changed = False

        if ds.changed:
            self.apply_debug_settings()
            ds.changed = False

        self.weather_data_streamer.update()
        self.scene.animate_all(delta_time)

        if self.level_of_detail.update(self.scene.camera, rs.projection):
            self.map_tiles.upload_instances(self.level_of_detail.render_instances)
            self.particles.upload_tree(self.level_of_detail.flat_tree)

        if rs.simulate_wind:
            particle_speed_factor = max(0.001, min(self.camera_movement.altitude / GLOBE_RADIUS, 1.0))
            self.particles.update(delta_time, particle_speed_factor)

    def apply_graphics_config(self, changes=None):
        def value(path):
            return changes.get(path, config.get(path)) if changes else config.get(path)

        msaa_samples = 4 if value("graphics.msaa_enabled") else 1
        shadow_map_resolution = value("graphics.shadow_map_resolution")
        shadow_cascade_count = value("graphics.shadow_cascade_count")

        self.frame_buffer.set_samples(msaa_samples)

        light_source = self.scene.light_source
        if (light_source.shadow_map_resolution != shadow_map_resolution
                or light_source.num_cascades != shadow_cascade_count):
            light_source.set_resolution(shadow_map_resolution, shadow_cascade_count)

        self.scene.ubo.update_ambient(value("graphics.ambient"))

    def update_celestial_objects(self, time):
        sun_direction = calculate_sun_direction(time)
        self.sun.entity.translation = sun_direction * 20 * GLOBE_RADIUS
        self.sun.entity.light_direction = sun_direction

        moon_direction = calculate_moon_direction(time)
        self.moon.entity.translation = moon_direction * 10 * GLOBE_RADIUS
        self.moon.entity.turn_to_vector(-moon_direction)

        sky_rotation = calculate_sky_rotation(time)
        self.sky.entity.rotation = sky_rotation
        self.atmosphere_shader.use()
        self.atmosphere_shader.set_mat3("skyRotation", glm.inverse(glm.mat3(glm.mat3_cast(sky_rotation))))

        self.scene.ubo.update_light_direction(sun_direction)

    def apply_render_settings(self):
        for k, v in self.scene.drawables.items():
            for plant_type in power_metadata_repository().plant_types:
                if k == f"power_point_{plant_type}":
                    v.hidden = not (
                        rs.render_power_plant_points
                        and rs.render_power_plants.get(plant_type, False)
                    )
                    v.color = rs.power_plant_colors[plant_type]
                    v.point_size = rs.power_plant_point_size
                elif k.startswith(f"power_model_{plant_type}_"):
                    v.hidden = not (
                        rs.render_power_plant_models
                        and rs.render_power_plants.get(plant_type, False)
                    )
                    v.shader_uniforms["modelScale"] = float(10 ** rs.model_scale)

        self.scene.drawables["power_grid"].hidden = not rs.render_power_grid
        self.scene.drawables["power_grid"].color = rs.power_grid_color

        self.scene.drawables["coast"].hidden = not rs.render_coastlines
        for id in BORDER_KEYS: self.scene.drawables[id].hidden = not rs.render_borders

        for shader in [self.scene.shaders["globe"], self.scene.shaders["polar_cap"]]:
            shader.use()
            shader.set_bool("useData", rs.render_data)
            shader.set_bool("showWind", rs.simulate_wind)
            shader.set_float("scaleStart", rs.scale_start)
            shader.set_float("scaleEnd", rs.scale_end)
            if rs.gradient: shader.textures["gradient"] = rs.gradient.texture

        for id in BORDER_KEYS + ["coast"]: self.scene.drawables[id].color = rs.border_color

        self.scene.ubo.update_projection(rs.projection.value)
        self.scene.ubo.update_vertical_scale(rs.vertical_scale)
        self.scene.ubo.update_shadows(rs.render_shadows)

        self.scene.enable_shadows = rs.render_shadows

        atmosphere_enabled = rs.should_render_atmosphere()
        celestial_objects_hidden = rs.projection != Projection.GLOBE
        self.sun.hidden = celestial_objects_hidden or atmosphere_enabled
        self.sky.hidden = celestial_objects_hidden or atmosphere_enabled
        self.moon.hidden = celestial_objects_hidden

        if rs.scalar_data_type is not None:
            if not rs.scalar_data_type.heights:
                rs.scalar_height_type = None
            elif rs.scalar_height_type not in rs.scalar_data_type.heights:
                rs.scalar_height_type = rs.scalar_data_type.heights[0]

        if rs.vector_data_type is not None:
            if not rs.vector_data_type.heights:
                rs.vector_height_type = None
            elif rs.vector_height_type not in rs.vector_data_type.heights:
                rs.vector_height_type = rs.vector_data_type.heights[0]

        if rs.scalar_data_type == SYNC_SCALAR:
            self.weather_data_streamer.set_data_types(rs.vector_data_type, rs.vector_height_type,
                                                      rs.vector_data_type, rs.vector_height_type)
        else:
            self.weather_data_streamer.set_data_types(rs.scalar_data_type, rs.scalar_height_type,
                                                      rs.vector_data_type, rs.vector_height_type)

        self.scene.shaders["cloud"].disabled = not rs.should_render_clouds()

        self.atmosphere_shader.disabled = not atmosphere_enabled

        self.particles.frame_buffer.update_size(rs.particle_resolution, rs.particle_resolution)
        self.particles.set_particle_speed(rs.particle_speed)
        self.particles.set_num_particles(rs.num_particles)

        if rs.simulate_wind:
            particle_texture = self.particles.frame_buffer.color_tex
            if particle_texture not in self.level_of_detail.fallbacks.targets:
                self.level_of_detail.fallbacks.targets.append(particle_texture)
        elif self.particles.frame_buffer.color_tex in self.level_of_detail.fallbacks.targets:
            self.level_of_detail.fallbacks.targets.remove(self.particles.frame_buffer.color_tex)

        if rs.camera_reset:
            self.scene.camera.translation = glm.dvec3(0, -2, 2) * GLOBE_RADIUS
            self.scene.camera.turn_to_vector(-self.scene.camera.translation)
            self.scene.camera.apply_view_transform()
            self.scene.camera.set_fov(config.graphics.default_fov)
            rs.camera_reset = False

    def apply_debug_settings(self):
        self.scene.shaders["globe"].use()
        self.scene.shaders["globe"].set_bool("drawDebug", ds.display_tile_boundaries)

    def destroy(self):
        self.weather_data_streamer.shutdown()
        self.level_of_detail.shutdown()
