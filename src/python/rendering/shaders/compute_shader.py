from OpenGL.GL import *

from rendering.shaders.base_shader import BaseShader
from rendering.shaders.shader_compiler import load_and_compile


class ComputeShader(BaseShader):
    def __init__(self, compute_path, defines=None):
        super().__init__()
        self._compile(compute_path, defines)

    def _compile(self, compute_path, defines):
        compute = load_and_compile(compute_path, GL_COMPUTE_SHADER, defines=defines)
        self._link_program(compute)

    def dispatch(self, x, y, z=1):
        self.use()
        glDispatchCompute(x, y, z)
