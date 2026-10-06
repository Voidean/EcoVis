import time

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from rendering.data.gl_data_format import ShaderBufferFormat, GlDataAttribute
from rendering.data.shader_buffer import FormattedShaderBuffer, ShaderBuffer
from rendering.shaders.compute_shader import ComputeShader
from rendering.shaders.shader import Shader
from rendering.textures.frame_buffer_array import FrameBufferArray
from util.config import config
from util.startup import checkpoint

PARTICLE_FORMAT = ShaderBufferFormat(
    GlDataAttribute("pos", glm.vec2),
    GlDataAttribute("old_pos", glm.vec2)
)

TREE_FORMAT = ShaderBufferFormat(
    GlDataAttribute("children", glm.ivec4),
    GlDataAttribute("layer_data", glm.ivec4)
)

START_TIME = time.perf_counter()


class Particles:
    def __init__(
        self,
        num_particles,
        frame_buffer_resolution,
        tiles_ssbo,
    ):
        self.particle_texture = None

        self.frame_buffer = FrameBufferArray(
            width=frame_buffer_resolution,
            height=frame_buffer_resolution,
            depth=config.graphics.tile_gpu_cache_size,
            channels=1, gl_format=GL_FLOAT,
            use_depth=False,
        )
        checkpoint()
        self.polar_frame_buffer = FrameBufferArray(
            width=4096, height=4096, depth=2,
            channels=1, gl_format=GL_FLOAT,
            use_depth=False,
        )
        checkpoint()

        self.update_position_shader = ComputeShader("Particle")
        checkpoint()

        self.particle_fade_shader = ComputeShader("ParticleFade")
        self.particle_polar_fade_shader = ComputeShader("ParticlePolarFade")
        checkpoint()

        self.particle_render_shader = Shader(
            "Particle", "Particle", "Particle",
            write_depth_buffer=False, additive_blend=True)
        self.particle_polar_render_shader = Shader(
            "ParticlePolar", "Particle", "ParticlePolar",
            write_depth_buffer=False, additive_blend=True)
        checkpoint()

        self.empty_vao = glGenVertexArrays(1)

        self.particle_ssbo = FormattedShaderBuffer(PARTICLE_FORMAT)
        self.tree_ssbo = FormattedShaderBuffer(TREE_FORMAT)
        self.tiles_ssbo = tiles_ssbo

        self.particle_speed = 1.0
        self.set_num_particles(num_particles)
        checkpoint()

        # Create your index pools (at max size matching particle limit)
        max_bytes = num_particles * 4  # uint32 entries
        self.polar_indices_ssbo = ShaderBuffer(data=np.zeros(num_particles, dtype=np.uint32))
        checkpoint()

        # Indirect draw commands initialized to: [count=0, instanceCount=1, first=0, baseInstance=0]
        cmd_init = np.array([0, 1, 0, 0], dtype=np.uint32)
        self.polar_cmd_buffer = ShaderBuffer(cmd_init, usage=GL_DYNAMIC_DRAW, target=GL_DRAW_INDIRECT_BUFFER)
        checkpoint()

    def set_num_particles(self, num_particles: int):
        if self.particle_ssbo.count == num_particles:
            return

        particles = np.zeros((num_particles, 8), dtype=np.float32)
        particles[:, 0:2] = particles[:, 4:6] = np.random.rand(num_particles, 2).astype(np.float32)
        particles[:, 2] = np.random.rand(num_particles).astype(np.float32)
        particles[:, 3] = np.random.rand(num_particles).astype(np.float32)

        self.particle_ssbo.direct_upload(particles.tobytes(), num_particles)

    def upload_tree(self, tree_data: np.ndarray):
        self.tree_ssbo.direct_upload(tree_data.tobytes(), len(tree_data))

    def set_particle_speed(self, speed: float):
        self.particle_speed = speed
        self.update_position_shader.use()
        self.update_position_shader.set_float("speedMultiplier", self.particle_speed)

    def update(self, dt, speed_factor=1.0):
        if self.particle_texture is None: return

        self.polar_cmd_buffer.buffer_sub_data(data=b'\x00\x00\x00\x00', offset=0)

        # Update Particle Positions (Compute)
        self.update_position_shader.use()

        glActiveTexture(GL_TEXTURE0)
        self.particle_texture.use()
        self.update_position_shader.set_int("vectorUV", 0)

        self.update_position_shader.set_float("deltaTime", dt)
        self.update_position_shader.set_float("speedMultiplier", self.particle_speed * speed_factor)

        self.update_position_shader.set_float("timeSeed", time.perf_counter() - START_TIME % 1000.0)
        self.update_position_shader.set_int("tileCount", self.tiles_ssbo.count)

        self.particle_ssbo.bind(0)
        self.tiles_ssbo.bind(1)
        self.polar_indices_ssbo.bind(2)
        self.polar_cmd_buffer.bind(3, target=GL_SHADER_STORAGE_BUFFER)

        self.update_position_shader.dispatch(self.particle_ssbo.count // 256, 1, 1)

        # Fade Particles
        if self.tiles_ssbo.count > 0:
            self.particle_fade_shader.use()

            self.frame_buffer.color_tex.bind_image(image_unit=0, access=GL_READ_WRITE)

            self.tiles_ssbo.bind(1)
            self.particle_fade_shader.set_float("fadeAmount", 0.06 ** dt)

            groups_x = self.frame_buffer.width // 16
            groups_y = self.frame_buffer.height // 16
            self.particle_fade_shader.dispatch(groups_x, groups_y, self.tiles_ssbo.count)

        # Fade Polar Particles
        self.particle_polar_fade_shader.use()

        self.polar_frame_buffer.color_tex.bind_image(image_unit=0, access=GL_READ_WRITE)
        self.particle_polar_fade_shader.set_float("fadeAmount", 0.06 ** dt)

        groups_x = self.polar_frame_buffer.width // 16
        groups_y = self.polar_frame_buffer.height // 16
        groups_z = 2

        self.particle_polar_fade_shader.dispatch(groups_x, groups_y, groups_z)

        # Render Particle Lines (Rasterize)
        self.frame_buffer.bind_all_layers()
        glBindVertexArray(self.empty_vao)

        self.particle_ssbo.bind(0)
        self.tree_ssbo.bind(1)  # Bind the QuadTree buffer for line layout mapping
        self.particle_render_shader.use()
        self.particle_render_shader.configure_settings()

        glMemoryBarrier(
            GL_SHADER_STORAGE_BARRIER_BIT |
            GL_SHADER_IMAGE_ACCESS_BARRIER_BIT |
            GL_COMMAND_BARRIER_BIT
        )

        glDrawArrays(GL_LINES, 0, self.particle_ssbo.count * 2)

        # Render Polar Particle Lines
        self.polar_frame_buffer.bind_all_layers()
        self.particle_polar_render_shader.use()

        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self.polar_cmd_buffer.id)
        glDrawArraysIndirect(GL_LINES, ctypes.c_void_p(0))

    def delete(self):
        self.particle_ssbo.delete()
        self.tree_ssbo.delete()
        glDeleteVertexArrays(1, [self.empty_vao])
