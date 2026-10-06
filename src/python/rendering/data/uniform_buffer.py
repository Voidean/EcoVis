from ctypes import c_ubyte

from OpenGL.GL import *
from rendering.data.gl_data_format import UniformBufferFormat


class UniformBuffer:
    def __init__(self, buffer_format: UniformBufferFormat, binding_point: int = 0):
        self.format = buffer_format
        self.binding_point = binding_point
        self.size = self.format.stride_bytes

        self.changed = False
        self.data = bytearray(self.size)

        self.id = glGenBuffers(1)
        glBindBuffer(GL_UNIFORM_BUFFER, self.id)
        glBufferData(GL_UNIFORM_BUFFER, self.size, None, GL_DYNAMIC_DRAW)
        glBindBufferBase(GL_UNIFORM_BUFFER, self.binding_point, self.id)

    def set_field(self, name: str, value):
        """Serializes a value and writes it at the correct format offset."""
        offset = self.format.offset_bytes(name)
        raw_bytes = self.format.serialize_field(name, value)

        if self.data[offset:offset + len(raw_bytes)] != raw_bytes:
            self.data[offset:offset + len(raw_bytes)] = raw_bytes
            self.changed = True

    def upload(self):
        """Uploads the local bytearray to the GPU if it has been modified."""
        if self.changed:
            self.changed = False
            glBindBuffer(GL_UNIFORM_BUFFER, self.id)
            buffer = (c_ubyte * self.size).from_buffer_copy(self.data)
            glBufferSubData(GL_UNIFORM_BUFFER, 0, self.size, buffer)

    def delete(self):
        glDeleteBuffers(1, [self.id])
