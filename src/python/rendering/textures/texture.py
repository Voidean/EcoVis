import math
import logging

import numpy as np
from OpenGL.GL import *
from PIL import Image

from rendering.textures.base_texture import BaseTexture
from rendering.textures.texture_formats import COLOR_INTERNAL_FORMATS, COLOR_FORMATS, numpy_to_gl_format
from util.paths import TEXTURES

logger = logging.getLogger(__name__)


def load_image_data(image) -> np.ndarray:
    if image.mode not in ("RGBA", "RGB", "L"): image = image.convert("RGBA")
    return np.array(image, dtype=np.uint8)


class Texture(BaseTexture):
    MAX_TEXTURE_SIZE = None

    def __init__(self, data: np.ndarray,
                 repeat_s=True, repeat_t=True,
                 mipmaps=True, keep_in_memory=False):

        if data.ndim == 2:
            data = data[:, :, None]

        self.data = data
        self.height, self.width, self.channels = data.shape

        if self.channels > 4: raise ValueError(f"Unsupported channel count: {self.channels}")

        self.gl_format = numpy_to_gl_format(data.dtype.type)
        self.internal_format = COLOR_INTERNAL_FORMATS[self.gl_format][self.channels]
        self.color_format = COLOR_FORMATS[self.channels]

        self.repeat_s = repeat_s
        self.repeat_t = repeat_t

        self.mipmaps = mipmaps
        self.levels = int(math.log2(max(self.width, self.height))) + 1 if self.mipmaps else 1

        self.keep_in_memory = keep_in_memory

        self.tex_id = None
        self.pbo = None
        self.mapped_ptr = None

        self.deleted = False

        self.tex_type = GL_TEXTURE_2D

    def upload(self):
        if self.tex_id is not None: return
        if self.data is None: raise RuntimeError()

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        glBindTexture(self.tex_type, 0)

        self.tex_id = glGenTextures(1)
        glBindTexture(self.tex_type, self.tex_id)

        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexStorage2D(self.tex_type, self.levels, self.internal_format, self.width, self.height)

        # Persistent Mapping
        self.pbo = glGenBuffers(1)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbo)

        flags = GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT
        glBufferStorage(GL_PIXEL_UNPACK_BUFFER, self.data.nbytes, None, flags | GL_DYNAMIC_STORAGE_BIT)
        self.mapped_ptr = glMapBufferRange(GL_PIXEL_UNPACK_BUFFER, 0, self.data.nbytes, flags)

        if not self.mapped_ptr: raise RuntimeError("glMapBufferRange failed")

        # Copy initial data
        gpu_view = np.frombuffer(
            (ctypes.c_char * self.data.nbytes).from_address(self.mapped_ptr),
            dtype=self.data.dtype
        ).reshape(self.height, self.width, self.channels)
        np.copyto(gpu_view, np.flipud(self.data))

        glTexSubImage2D(self.tex_type, 0, 0, 0, self.width, self.height, self.color_format, self.gl_format, None)

        if self.mipmaps: glGenerateMipmap(self.tex_type)
        glTexParameteri(self.tex_type, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR if self.mipmaps else GL_LINEAR)
        glTexParameteri(self.tex_type, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(self.tex_type, GL_TEXTURE_WRAP_S, GL_REPEAT if self.repeat_s else GL_CLAMP_TO_EDGE)
        glTexParameteri(self.tex_type, GL_TEXTURE_WRAP_T, GL_REPEAT if self.repeat_t else GL_CLAMP_TO_EDGE)

        glBindTexture(self.tex_type, 0)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        if not self.keep_in_memory: self.data = None  # delete data from normal RAM after uploading to VRAM

    def update_data(self, data: np.ndarray):
        if not self.mapped_ptr: return

        if data.ndim == 2:
            data = data[:, :, None]

        if data.shape != (self.height, self.width, self.channels) or self.gl_format != numpy_to_gl_format(data.dtype):
            self.delete()
            self.deleted = False

            self.data = data
            self.height, self.width, self.channels = data.shape
            self.levels = int(math.log2(max(self.width, self.height))) + 1 if self.mipmaps else 1

            self.gl_format = numpy_to_gl_format(data.dtype)
            self.internal_format = COLOR_INTERNAL_FORMATS[self.gl_format][self.channels]
            self.color_format = COLOR_FORMATS[self.channels]

            self.upload()
            return

        if self.keep_in_memory: self.data = data

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        glBindTexture(self.tex_type, 0)

        # Update the persistent memory
        gpu_view = np.frombuffer(
            (ctypes.c_char * data.nbytes).from_address(self.mapped_ptr),
            dtype=data.dtype
        ).reshape(self.height, self.width, self.channels)
        np.copyto(gpu_view, np.flipud(data))

        # Refresh the texture from the PBO
        glBindTexture(self.tex_type, self.tex_id)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbo)

        glTexSubImage2D(self.tex_type, 0, 0, 0, self.width, self.height, self.color_format, self.gl_format, None)
        if self.mipmaps: glGenerateMipmap(self.tex_type)

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        glBindTexture(self.tex_type, 0)

    def use(self, texture_unit=0):
        if self.deleted:
            Texture.empty().use(texture_unit)
            logger.error("Tried to use deleted texture")
            return

        if self.tex_id is None: self.upload()

        glActiveTexture(GL_TEXTURE0 + texture_unit)
        glBindTexture(GL_TEXTURE_2D, self.tex_id)

    def bind_image(self, image_unit, access=GL_READ_WRITE, level=0, layer=0):
        if self.tex_id is None: self.upload()

        glBindImageTexture(image_unit, self.tex_id, level, GL_FALSE, layer, access, self.internal_format)

    def get_id(self):
        if self.tex_id is None: self.upload()
        return self.tex_id

    def delete(self):
        self.deleted = True
        self.data = None
        if self.tex_id:
            glDeleteTextures([self.tex_id])
            self.tex_id = None
        if self.pbo:
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbo)
            glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)
            glDeleteBuffers(1, [self.pbo])
            self.pbo = None
            self.mapped_ptr = None

    @classmethod
    def from_image(cls, image, repeat_s=True, repeat_t=True, mipmaps=True):
        return cls(load_image_data(image), repeat_s=repeat_s, repeat_t=repeat_t, mipmaps=mipmaps)

    @classmethod
    def from_file(cls, filepath, repeat_s=True, repeat_t=True, mipmaps=True):
        try:
            image = Image.open(TEXTURES / filepath)
        except Exception:
            logger.error("Missing texture at %s", TEXTURES / filepath)
            return Texture.empty()

        max_size = Texture.MAX_TEXTURE_SIZE
        if max_size is not None and (image.width > max_size or image.height > max_size):
            scale = min(max_size / image.width, max_size / image.height)
            image = image.resize((int(image.width * scale), int(image.height * scale)), Image.BILINEAR)

        return cls(load_image_data(image), repeat_s=repeat_s, repeat_t=repeat_t, mipmaps=mipmaps)

    _empty = None

    @classmethod
    def empty(cls):
        if cls._empty is None:
            data = np.full((1, 1, 4), 255, dtype=np.uint8)
            cls._empty = cls(data)
        return cls._empty

    _empty_normal = None

    @classmethod
    def empty_normal(cls):
        if cls._empty_normal is None:
            data = np.full((1, 1, 3), (128, 128, 255), dtype=np.uint8)
            cls._empty_normal = cls(data)
        return cls._empty_normal
