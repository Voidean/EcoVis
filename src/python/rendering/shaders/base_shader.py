from abc import ABC

from OpenGL.GL import *

from rendering.data.gl_types import GL_TYPES
from rendering.shaders.shader_error import ShaderLinkingError


class BaseShader(ABC):
    def __init__(self):
        self.id = glCreateProgram()
        self.textures = {}  # key: id as String, value: Texture

    def use(self):
        glUseProgram(self.id)

    def use_textures(self):
        for unit, (tex_name, tex) in enumerate(self.textures.items()):
            tex.use(unit)
            self.set_int(tex_name, unit)

    def _link_program(self, *shaders):
        for shader in shaders: glAttachShader(self.id, shader)

        glLinkProgram(self.id)

        success = glGetProgramiv(self.id, GL_LINK_STATUS)
        if not success:
            log = glGetProgramInfoLog(self.id).decode()
            raise ShaderLinkingError(log)

        for shader in shaders: glDeleteShader(shader)

    def bind_ubo(self, block_name, binding_point=0):
        block_index = glGetUniformBlockIndex(self.id, block_name)
        if block_index != GL_INVALID_INDEX:
            glUniformBlockBinding(self.id, block_index, binding_point)

    def uni_loc(self, name: str):
        return glGetUniformLocation(self.id, name)

    def uni_array_loc(self, name: str):
        location = self.uni_loc(name)
        if location < 0:
            location = self.uni_loc(f"{name}[0]")
        return location

    def set_uniform(self, name: str, value):
        GL_TYPES[type(value)].uniform_setter(self.uni_loc(name), value)

    def set_uniform_array(self, name: str, type_: type, values):
        GL_TYPES[type_].uniform_array_setter(self.uni_array_loc(name), values)

    def delete(self):
        glDeleteProgram(self.id)


def _make_uniform_method(info):
    def setter(self, name: str, value):
        info.uniform_setter(self.uni_loc(name), value)

    setter.__name__ = f"set_{info.name}"
    setter.__qualname__ = f"BaseShader.set_{info.name}"
    return setter


def _make_uniform_array_method(info):
    def setter(self, name: str, values):
        info.uniform_array_setter(self.uni_array_loc(name), values)

    setter.__name__ = f"set_{info.name}_array"
    setter.__qualname__ = f"BaseShader.set_{info.name}_array"
    return setter


for info in GL_TYPES.values():
    setattr(BaseShader, f"set_{info.name}", _make_uniform_method(info))
    setattr(BaseShader, f"set_{info.name}_array", _make_uniform_array_method(info))
