import numpy as np
from OpenGL.GL import *

from rendering.scene.camera import Camera
from rendering.shaders.base_shader import BaseShader
from rendering.shaders.shader_compiler import load_and_compile


def _init_quad_vao():
    if Shader.quad_vao is None:
        quad_data = np.array([
            -1.0,  1.0, 0.0,    0.0, 1.0,
            -1.0, -1.0, 0.0,    0.0, 0.0,
             1.0,  1.0, 0.0,    1.0, 1.0,
             1.0, -1.0, 0.0,    1.0, 0.0,
        ], dtype=np.float32)

        Shader.quad_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)

        glBindVertexArray(Shader.quad_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_data.nbytes, quad_data, GL_STATIC_DRAW)

        # Position attribute
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(0))
        # TexCoord attribute
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(3 * 4))
        glBindVertexArray(0)


class Shader(BaseShader):
    quad_vao = None

    def __init__(self, vertex_name, fragment_name, geometry_name=None,
                 defines=None,
                 double_sided=False,
                 additive_blend=False,
                 custom_blend=False,
                 transmittance_blend=False,
                 write_depth_buffer=True,
                 frustum_culling=True):
        super().__init__()

        self.disabled = False

        self.drawables = []
        self.default_drawable_uniforms = {}

        self.double_sided = double_sided
        self.additive_blend = additive_blend
        self.custom_blend = custom_blend
        self.transmittance_blend = transmittance_blend
        self.write_depth_buffer = write_depth_buffer
        self.enable_culling = frustum_culling

        _init_quad_vao()

        self._compile(vertex_name, fragment_name, geometry_name, defines)

    def _compile(self, vertex_name, fragment_name, geometry_name, defines):
        vertex = load_and_compile(vertex_name, GL_VERTEX_SHADER, defines)
        fragment = load_and_compile(fragment_name, GL_FRAGMENT_SHADER, defines)

        if geometry_name:
            geometry = load_and_compile(geometry_name, GL_GEOMETRY_SHADER, defines)
            self._link_program(vertex, geometry, fragment)
        else:
            self._link_program(vertex, fragment)

    def configure_settings(self):
        if self.double_sided:
            glDisable(GL_CULL_FACE)
        else:
            glEnable(GL_CULL_FACE)

        if self.transmittance_blend:
            # The second fragment output contains RGB transmittance, yielding
            # atmosphere + scene * transmittance in one blend operation.
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ONE, GL_SRC1_COLOR)
        elif not self.custom_blend:
            if self.additive_blend:
                glBlendFunc(GL_ONE, GL_ONE)
            else:
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if self.write_depth_buffer:
            glDepthMask(GL_TRUE)
        else:
            glDepthMask(GL_FALSE)

    def draw_all(self, frustum_planes=None, cull_view_pos=None):
        self.configure_settings()
        self.use_textures()
        for drawable in self.drawables:
            if not drawable.hidden:
                drawable.apply_shader_uniforms(self, self.default_drawable_uniforms)
                drawable.draw(self, self.enable_culling, frustum_planes, cull_view_pos)

    def draw_fullscreen(self):
        self.configure_settings()
        self.use_textures()
        glDisable(GL_DEPTH_TEST)
        glBindVertexArray(Shader.quad_vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)
