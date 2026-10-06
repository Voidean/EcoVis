import logging

import numpy as np
from OpenGL.GL import *

from rendering.textures.base_texture import BaseTexture
from rendering.textures.texture_formats import COLOR_INTERNAL_FORMATS, COLOR_FORMATS, numpy_to_gl_format, GL_FORMAT_BYTE_SIZES

logger = logging.getLogger(__name__)


class TextureArray(BaseTexture):
    def __init__(self, width: int, height: int, channels: int, depth: int, dtype=np.uint8,
                 repeat_s=False, repeat_t=False, num_pbos=8):
        """
        depth: The maximum number of textures this array can hold.
        All textures in the array MUST share the same width, height, and format.
        """
        self.width = width
        self.height = height
        self.channels = channels
        self.depth = depth

        self.dtype = dtype

        self.gl_format = numpy_to_gl_format(dtype)
        self.internal_format = COLOR_INTERNAL_FORMATS[self.gl_format][self.channels]
        self.color_format = COLOR_FORMATS[self.channels]

        self.repeat_s = repeat_s
        self.repeat_t = repeat_t

        self.tex_id = None
        self.layer_bytes = 0

        self.deleted = False

        self.num_pbos = num_pbos
        self.pbos = [None] * self.num_pbos
        self.mapped_ptrs = [None] * self.num_pbos
        self.sync_objs = [None] * self.num_pbos
        self.next_pbo_idx = 0

        self.tex_type = GL_TEXTURE_2D_ARRAY

    def allocate(self):
        """Allocates the immutable GPU storage and the single-layer PBO."""
        if self.tex_id is not None: return

        self.tex_id = glGenTextures(1)
        glBindTexture(self.tex_type, self.tex_id)

        levels = 1  # (no mipmaps)
        glTexStorage3D(self.tex_type, levels, self.internal_format,
                       self.width, self.height, self.depth)

        glTexParameteri(self.tex_type, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(self.tex_type, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(self.tex_type, GL_TEXTURE_WRAP_S, GL_REPEAT if self.repeat_s else GL_CLAMP_TO_EDGE)
        glTexParameteri(self.tex_type, GL_TEXTURE_WRAP_T, GL_REPEAT if self.repeat_t else GL_CLAMP_TO_EDGE)

        glBindTexture(self.tex_type, 0)

        self.layer_bytes = self.width * self.height * self.channels * GL_FORMAT_BYTE_SIZES[self.gl_format]

        # Create multiple PBOs exactly large enough to hold one layer
        for i in range(self.num_pbos):
            pbo = glGenBuffers(1)
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)

            flags = GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT
            glBufferStorage(GL_PIXEL_UNPACK_BUFFER, self.layer_bytes, None, flags | GL_DYNAMIC_STORAGE_BIT)

            self.pbos[i] = pbo
            self.mapped_ptrs[i] = glMapBufferRange(GL_PIXEL_UNPACK_BUFFER, 0, self.layer_bytes, flags)

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

    def update_layer(self, layer_index: int, data: np.ndarray):
        """Inserts a single texture's numpy data into the specified layer index."""
        if self.tex_id is None: self.allocate()

        if data.ndim == 2:
            data = data[:, :, None]

        if data.shape != (self.height, self.width, self.channels):
            raise ValueError(
                f"Data shape {data.shape} does not match array dimensions {(self.height, self.width, self.channels)}")
        if numpy_to_gl_format(data.dtype) != self.gl_format:
            raise ValueError("Data format does not match array format.")

        # Select next PBO
        pbo_idx = self.next_pbo_idx
        self.next_pbo_idx = (self.next_pbo_idx + 1) % self.num_pbos

        # Wait only if this specific PBO is still being read by GPU
        if self.sync_objs[pbo_idx]:
            glClientWaitSync(self.sync_objs[pbo_idx], GL_SYNC_FLUSH_COMMANDS_BIT, 1_000_000_000)
            glDeleteSync(self.sync_objs[pbo_idx])
            self.sync_objs[pbo_idx] = None

        # Copy data to current PBO
        gpu_view = np.frombuffer(
            (ctypes.c_char * data.nbytes).from_address(self.mapped_ptrs[pbo_idx]),
            dtype=self.dtype
        ).reshape(self.height, self.width, self.channels)
        np.copyto(gpu_view, np.flipud(data))

        # Upload
        glBindTexture(self.tex_type, self.tex_id)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[pbo_idx])

        glTexSubImage3D(self.tex_type, 0, 0, 0, layer_index,
                        self.width, self.height, 1, self.color_format,
                        self.gl_format, None)

        # Create Fence for this PBO
        self.sync_objs[pbo_idx] = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
        glFlush()

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        glBindTexture(self.tex_type, 0)

    def use(self, texture_unit=0):
        if self.deleted:
            logger.error("Tried to use deleted texture")
            return

        if self.tex_id is None: self.allocate()

        glActiveTexture(GL_TEXTURE0 + texture_unit)
        glBindTexture(self.tex_type, self.tex_id)

    def bind_image(self, image_unit, access=GL_READ_WRITE, level=0, layer=0):
        if self.tex_id is None: self.allocate()

        glBindImageTexture(image_unit, self.tex_id, level, GL_TRUE, layer, access, self.internal_format)

    def delete(self):
        self.deleted = True

        if self.tex_id is not None:
            glDeleteTextures([self.tex_id])
            self.tex_id = None

        for sync in self.sync_objs:
            if sync:
                glDeleteSync(sync)
        self.sync_objs = [None] * self.num_pbos

        for i, pbo in enumerate(self.pbos):
            if pbo and self.mapped_ptrs[i]:
                glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
                glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        valid_pbos = [pbo for pbo in self.pbos if pbo is not None]
        if valid_pbos:
            glDeleteBuffers(len(valid_pbos), valid_pbos)

        self.pbos = [None] * self.num_pbos
        self.mapped_ptrs = [None] * self.num_pbos
