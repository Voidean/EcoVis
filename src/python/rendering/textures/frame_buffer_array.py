from OpenGL.GL import *

from rendering.textures.base_texture import TextureHandle
from rendering.textures.texture_formats import COLOR_INTERNAL_FORMATS, COLOR_FORMATS
from rendering.textures.texture import Texture


class FrameBufferArray:
    def __init__(self, width, height, depth, channels=4, gl_format=GL_UNSIGNED_BYTE,
                 use_color=True, use_depth=True, repeat_s=False, repeat_t=False):
        self.use_color = use_color
        self.use_depth = use_depth

        self.repeat_s = repeat_s
        self.repeat_t = repeat_t

        self.gl_format = gl_format
        color_internal_format = COLOR_INTERNAL_FORMATS[self.gl_format][channels]
        self.color_format = COLOR_FORMATS[channels]

        self.id = glGenFramebuffers(1)

        self.color_tex = TextureHandle(height, width, channels, depth, tex_type=GL_TEXTURE_2D_ARRAY, internal_format=color_internal_format)
        self.depth_tex = TextureHandle(height, width, 1, depth, tex_type=GL_TEXTURE_2D_ARRAY, internal_format=GL_DEPTH_COMPONENT32F)

        self.update_size(width, height, depth)

    @property
    def width(self):
        return self.color_tex.width

    @property
    def height(self):
        return self.color_tex.height

    @property
    def depth(self):
        return self.color_tex.depth

    @property
    def channels(self):
        return self.color_tex.channels

    def update_size(self, width, height, depth=None):
        if self.color_tex.tex_id is not None and width == self.width and height == self.height and (depth is None or depth == self.depth):
            return

        self.color_tex.width = self.depth_tex.width = max(1, min(width, Texture.MAX_TEXTURE_SIZE))
        self.color_tex.height = self.depth_tex.height = max(1, min(height, Texture.MAX_TEXTURE_SIZE))
        if depth is not None:
            self.color_tex.depth = self.depth_tex.depth = max(1, min(depth, Texture.MAX_TEXTURE_SIZE))

        if self.use_color:
            self._init_texture(self.color_tex)
        if self.use_depth:
            self._init_texture(self.depth_tex)

    def _init_texture(self, tex: TextureHandle):
        tex.delete()
        tex.tex_id = glGenTextures(1)
        glBindTexture(tex.tex_type, tex.tex_id)

        glTexStorage3D(tex.tex_type, 1, tex.internal_format, tex.width, tex.height, tex.depth)
        filter_mode = GL_NEAREST if tex.internal_format == GL_DEPTH_COMPONENT32F else GL_LINEAR
        glTexParameteri(tex.tex_type, GL_TEXTURE_MIN_FILTER, filter_mode)
        glTexParameteri(tex.tex_type, GL_TEXTURE_MAG_FILTER, filter_mode)
        glTexParameteri(tex.tex_type, GL_TEXTURE_WRAP_S, GL_REPEAT if self.repeat_s else GL_CLAMP_TO_EDGE)
        glTexParameteri(tex.tex_type, GL_TEXTURE_WRAP_T, GL_REPEAT if self.repeat_t else GL_CLAMP_TO_EDGE)

    def bind_layer(self, layer_index):
        if layer_index < 0 or layer_index >= self.depth:
            raise ValueError(f"Layer index {layer_index} out of bounds for array depth {self.depth}")

        glBindFramebuffer(GL_FRAMEBUFFER, self.id)
        if self.use_color:
            glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, self.color_tex.tex_id, 0, layer_index)
        if self.use_depth:
            glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, self.depth_tex.tex_id, 0, layer_index)
        glViewport(0, 0, self.width, self.height)
        if self.use_color:
            glDrawBuffers(1, [GL_COLOR_ATTACHMENT0])
        else:
            glDrawBuffer(GL_NONE)
            glReadBuffer(GL_NONE)

    def bind_all_layers(self):
        """Attaches the entire array to the FBO. Requires a Geometry Shader using gl_Layer to target specific slices."""
        glBindFramebuffer(GL_FRAMEBUFFER, self.id)
        if self.use_color:
            glFramebufferTexture(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, self.color_tex.tex_id, 0)
        if self.use_depth:
            glFramebufferTexture(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, self.depth_tex.tex_id, 0)
        glViewport(0, 0, self.width, self.height)
        if self.use_color:
            glDrawBuffers(1, [GL_COLOR_ATTACHMENT0])
        else:
            glDrawBuffer(GL_NONE)
            glReadBuffer(GL_NONE)

    def delete(self):
        self.color_tex.delete()
        self.depth_tex.delete()

        if self.id:
            glDeleteFramebuffers(1, [self.id])
            self.id = None
