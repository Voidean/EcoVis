from typing import Self

import numpy as np
from OpenGL.GL import *

from rendering.data.gl_types import GL_TYPES
from rendering.data.shader_buffer import ShaderBuffer
from rendering.geometry.geometry_data import GeometryData
from rendering.data.gl_data_format import VertexFormat


class Geometry:
    def __init__(self, vertex_array: np.ndarray, index_array: np.ndarray,
                 vertex_format: VertexFormat, base_radius: float | None = None):
        self.vertex_format = vertex_format
        self.base_radius = base_radius

        self.count = len(index_array)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        self.upload(vertex_array, index_array)

    def upload(self, vertex_array, index_array):
        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertex_array.nbytes, vertex_array, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, index_array.nbytes, index_array, GL_STATIC_DRAW)

        for location, attr in enumerate(self.vertex_format.attributes):
            info = GL_TYPES[attr.type]

            if attr.type is int or info.name.startswith("i"):
                glVertexAttribIPointer(location, attr.size, GL_INT,
                                       self.vertex_format.stride_bytes,
                                       ctypes.c_void_p(self.vertex_format.offset_bytes(attr.name)))
            else:
                glVertexAttribPointer(location, attr.size, GL_FLOAT, GL_FALSE,
                                      self.vertex_format.stride_bytes,
                                      ctypes.c_void_p(self.vertex_format.offset_bytes(attr.name)))

            glEnableVertexAttribArray(location)

        glBindVertexArray(0)

    def use(self):
        glBindVertexArray(self.vao)

    def draw(self, primitive=GL_TRIANGLES):
        glDrawElements(primitive, self.count, GL_UNSIGNED_INT, ctypes.c_void_p(0))

    def draw_instanced(self, instance_count, primitive=GL_TRIANGLES):
        glDrawElementsInstanced(primitive, self.count, GL_UNSIGNED_INT, ctypes.c_void_p(0), instance_count)

    def draw_indirect(self, command_buffer: ShaderBuffer, primitive=GL_TRIANGLES):
        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, command_buffer.id)
        glDrawElementsIndirect(primitive, GL_UNSIGNED_INT, ctypes.c_void_p(0))

    def delete(self):
        glDeleteVertexArrays(1, [self.vao])
        glDeleteBuffers(1, [self.vbo])
        glDeleteBuffers(1, [self.ebo])

    @classmethod
    def from_data(cls, geometry: GeometryData | Self) -> Self:
        if isinstance(geometry, cls):
            return geometry
        elif isinstance(geometry, GeometryData):
            return cls(geometry.get_vertex_array(), geometry.get_index_array(), geometry.vertex_format,
                       geometry.base_radius)
        else:
            raise TypeError
