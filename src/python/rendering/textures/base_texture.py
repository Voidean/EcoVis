from abc import ABC
from OpenGL.GL import *

from rendering.textures.texture_formats import GL_TO_GLSL_FORMAT


class BaseTexture(ABC):
    tex_id: int | None
    tex_type: int
    internal_format: int

    height: int
    width: int
    depth: int | None = None
    channels: int

    def use(self, texture_unit):
        glActiveTexture(GL_TEXTURE0 + texture_unit)
        glBindTexture(self.tex_type, self.tex_id)

    def bind_image(self, image_unit, access=GL_READ_WRITE, level=0, layer=0):
        layered = GL_TRUE if self.tex_type in (GL_TEXTURE_2D_ARRAY, GL_TEXTURE_3D, GL_TEXTURE_CUBE_MAP) else GL_FALSE
        glBindImageTexture(image_unit, self.tex_id, level, layered, layer, access, self.internal_format)

    def delete(self):
        if self.tex_id:
            glDeleteTextures(1, [self.tex_id])
            self.tex_id = None

    @property
    def glsl_format(self):
        return GL_TO_GLSL_FORMAT[self.internal_format]


class TextureHandle(BaseTexture):
    def __init__(self, height, width, channels, depth=None, tex_id=None, tex_type=GL_TEXTURE_2D, internal_format=GL_RGBA8):
        self.height = height
        self.width = width
        self.depth = depth
        self.channels = channels

        self.tex_id = tex_id
        self.tex_type = tex_type
        self.internal_format = internal_format
