from OpenGL.GL import *

from rendering.data.gl_data_format import GlDataRecord, ShaderBufferFormat


class ShaderBuffer:
    def __init__(self, data=None, usage=GL_DYNAMIC_DRAW, target=GL_SHADER_STORAGE_BUFFER):
        self.id = glGenBuffers(1)
        self.usage = usage
        self.target = target

        if data is not None:
            self.buffer_data(data)

    def bind(self, binding, target=None):
        glBindBufferBase(target if target is not None else self.target, binding, self.id)

    def buffer_data(self, data):
        glBindBuffer(self.target, self.id)
        glBufferData(self.target, data.nbytes, data, self.usage)

    def buffer_sub_data(self, data: bytes, offset=0):
        glBindBuffer(self.target, self.id)
        glBufferSubData(self.target, offset, len(data), data)

    def delete(self):
        glDeleteBuffers(1, [self.id])


class FormattedShaderBuffer(ShaderBuffer):
    def __init__(self, data_format: ShaderBufferFormat, usage=GL_DYNAMIC_DRAW, target=GL_SHADER_STORAGE_BUFFER):
        super().__init__(usage=usage, target=target)
        self.format = data_format

        self.capacity_bytes = 0  # Total VRAM allocated
        self.count = 0  # Number of elements currently stored

    @property
    def occupied_bytes(self) -> int:
        """The actual bytes occupied by the valid records."""
        return self.count * self.format.stride_bytes

    def reserve(self, target_capacity_bytes: int):
        """Grows the GPU buffer capacity exponentially, preserving existing data via GPU-to-GPU copy."""
        if target_capacity_bytes <= self.capacity_bytes:
            return

        # Growth strategy: double the size, with a starting minimum
        new_capacity = max(self.capacity_bytes * 2, 512)
        while new_capacity < target_capacity_bytes:
            new_capacity *= 2

        # Create a new buffer with the larger capacity
        new_id = glGenBuffers(1)
        glBindBuffer(self.target, new_id)
        glBufferData(self.target, new_capacity, None, self.usage)

        # If we have existing data, copy it directly on the GPU
        if self.occupied_bytes > 0:
            glBindBuffer(GL_COPY_READ_BUFFER, self.id)
            glBindBuffer(GL_COPY_WRITE_BUFFER, new_id)
            glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER, 0, 0, self.occupied_bytes)
            glBindBuffer(GL_COPY_READ_BUFFER, 0)
            glBindBuffer(GL_COPY_WRITE_BUFFER, 0)

        # Delete the old layout container and swap IDs
        self.delete()
        self.id = new_id
        self.capacity_bytes = new_capacity

    def append_record(self, record: GlDataRecord) -> int:
        """Appends a record, automatically resizing via GPU if necessary. Returns the allocated index."""
        next_index = self.count
        required_size = (next_index + 1) * self.format.stride_bytes

        if required_size > self.capacity_bytes:
            self.reserve(required_size)

        # Serialize and write only the new record to the end of our current valid data range
        offset = next_index * self.format.stride_bytes
        data = self.format.serialize(record)

        self.buffer_sub_data(data, offset)

        self.count += 1
        return next_index

    def upload_records(self, records: list[GlDataRecord]):
        """Helper to overwrite/initialize the buffer with a full list of records at once."""
        stride = self.format.stride_bytes
        total_needed = len(records) * stride

        self.reserve(total_needed)

        batch_bytes = bytearray(total_needed)
        for i, record in enumerate(records):
            batch_bytes[i * stride: (i + 1) * stride] = self.format.serialize(record)
        data = bytes(batch_bytes)

        self.buffer_sub_data(data)
        self.count = len(records)

    def update_record(self, index: int, record: GlDataRecord):
        offset = index * self.format.stride_bytes
        data = self.format.serialize(record)
        self.buffer_sub_data(data, offset)

    def update_field(self, index: int, field_name: str, value):
        offset = (index * self.format.stride_bytes) + self.format.offset_bytes(field_name)
        data = self.format.serialize_field(field_name, value)
        self.buffer_sub_data(data, offset)

    def direct_upload(self, data: bytes, count: int):
        self.reserve(len(data))
        self.buffer_sub_data(data)
        self.count = count
