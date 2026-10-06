import logging

from OpenGL.GL import *
from rendering.textures.base_texture import TextureHandle
from rendering.textures.texture_formats import COLOR_INTERNAL_FORMATS, COLOR_FORMATS
from rendering.textures.texture import Texture

logger = logging.getLogger(__name__)


class FrameBuffer:
    def __init__(self, width, height, channels=4, samples=1, gl_format=GL_UNSIGNED_BYTE,
                 use_color=True, use_depth=True, repeat_s=False, repeat_t=False):
        self.samples = samples

        self.use_color = use_color
        self.use_depth = use_depth

        self.repeat_s = repeat_s
        self.repeat_t = repeat_t

        color_internal_format = COLOR_INTERNAL_FORMATS[gl_format][channels]
        self.color_internal_format = color_internal_format

        self.id = glGenFramebuffers(1)
        self.resolve_id = glGenFramebuffers(1) if samples > 1 else None

        # Final textures (Resolved targets if MSAA, main targets if not)
        self.color_tex = TextureHandle(height, width, channels, tex_type=GL_TEXTURE_2D,
                                       internal_format=color_internal_format)
        self.depth_tex = TextureHandle(height, width, 1, tex_type=GL_TEXTURE_2D,
                                       internal_format=GL_DEPTH_COMPONENT32F)

        # MSAA textures (Only used as render targets, never read directly)
        self.msaa_color_tex = TextureHandle(height, width, channels, tex_type=GL_TEXTURE_2D_MULTISAMPLE,
                                            internal_format=color_internal_format) if samples > 1 else None
        self.msaa_depth_tex = TextureHandle(height, width, 1, tex_type=GL_TEXTURE_2D_MULTISAMPLE,
                                            internal_format=GL_DEPTH_COMPONENT32F) if samples > 1 else None

        self.update_size(width, height)

    @property
    def width(self):
        return self.color_tex.width

    @property
    def height(self):
        return self.color_tex.height

    @property
    def channels(self):
        return self.color_tex.channels

    def set_samples(self, samples):
        if self.samples == samples: return
        self.samples = samples

        # Ensure resolve FBO exists if MSAA is turned on dynamically
        if self.samples > 1 and not self.resolve_id:
            self.resolve_id = glGenFramebuffers(1)
            self.msaa_color_tex = TextureHandle(self.height, self.width, self.channels,
                                                tex_type=GL_TEXTURE_2D_MULTISAMPLE,
                                                internal_format=self.color_internal_format)
            self.msaa_depth_tex = TextureHandle(self.height, self.width, 1,
                                                tex_type=GL_TEXTURE_2D_MULTISAMPLE,
                                                internal_format=GL_DEPTH_COMPONENT32F)

        self.update_size(self.width, self.height, force_update=True)

    def update_size(self, width, height, force_update=False):
        # Prevent redundant updates
        if not force_update and self.color_tex.tex_id is not None and width == self.width and height == self.height:
            return

        new_w = max(1, min(width, Texture.MAX_TEXTURE_SIZE or float('inf')))
        new_h = max(1, min(height, Texture.MAX_TEXTURE_SIZE or float('inf')))

        self.color_tex.width = self.depth_tex.width = new_w
        self.color_tex.height = self.depth_tex.height = new_h

        if self.samples > 1:
            self.msaa_color_tex.width = self.msaa_depth_tex.width = new_w
            self.msaa_color_tex.height = self.msaa_depth_tex.height = new_h

        # Initialize Textures
        if self.samples > 1:
            if self.use_color:
                self._init_texture(self.msaa_color_tex, multisample=True)
            if self.use_depth:
                self._init_texture(self.msaa_depth_tex, multisample=True)

        if self.use_color: self._init_texture(self.color_tex, multisample=False)
        if self.use_depth: self._init_texture(self.depth_tex, multisample=False)

        # Attach to Main FBO
        glBindFramebuffer(GL_FRAMEBUFFER, self.id)
        target_color = self.msaa_color_tex if self.samples > 1 else self.color_tex
        target_depth = self.msaa_depth_tex if self.samples > 1 else self.depth_tex

        if self.use_color:
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, target_color.tex_type, target_color.tex_id, 0)
        if self.use_depth:
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, target_depth.tex_type, target_depth.tex_id, 0)

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            logger.error("Main framebuffer not complete!")

        # Attach to Resolve FBO
        if self.samples > 1:
            glBindFramebuffer(GL_FRAMEBUFFER, self.resolve_id)
            if self.use_color:
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_tex.tex_id, 0)
            if self.use_depth:
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, self.depth_tex.tex_id, 0)

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            logger.error("Resolve framebuffer not complete!")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def _init_texture(self, tex: TextureHandle, multisample: bool):
        tex.delete()
        tex.tex_id = glGenTextures(1)
        glBindTexture(tex.tex_type, tex.tex_id)

        if multisample:
            glTexStorage2DMultisample(tex.tex_type, self.samples, tex.internal_format, tex.width, tex.height, GL_TRUE)
        else:
            glTexStorage2D(tex.tex_type, 1, tex.internal_format, tex.width, tex.height)
            filter_mode = GL_NEAREST if tex.internal_format == GL_DEPTH_COMPONENT32F else GL_LINEAR
            glTexParameteri(tex.tex_type, GL_TEXTURE_MIN_FILTER, filter_mode)
            glTexParameteri(tex.tex_type, GL_TEXTURE_MAG_FILTER, filter_mode)
            glTexParameteri(tex.tex_type, GL_TEXTURE_WRAP_S, GL_REPEAT if self.repeat_s else GL_CLAMP_TO_EDGE)
            glTexParameteri(tex.tex_type, GL_TEXTURE_WRAP_T, GL_REPEAT if self.repeat_t else GL_CLAMP_TO_EDGE)

        glBindTexture(tex.tex_type, 0)

    def resolve(self):
        if self.samples > 1:
            glBindFramebuffer(GL_READ_FRAMEBUFFER, self.id)
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.resolve_id)

            flags = (GL_COLOR_BUFFER_BIT if self.use_color else 0) | (GL_DEPTH_BUFFER_BIT if self.use_depth else 0)
            glBlitFramebuffer(0, 0, self.width, self.height, 0, 0, self.width, self.height, flags, GL_NEAREST)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def copy_to_screen(self):
        read_id = self.resolve_id if self.samples > 1 else self.id
        glBindFramebuffer(GL_READ_FRAMEBUFFER, read_id)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)
        glBlitFramebuffer(0, 0, self.width, self.height, 0, 0, self.width, self.height, GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.id)
        glViewport(0, 0, self.width, self.height)
        if self.use_color:
            glDrawBuffers(1, [GL_COLOR_ATTACHMENT0])
        else:
            glDrawBuffer(GL_NONE)
            glReadBuffer(GL_NONE)

    def bind_resolved(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.resolve_id if self.samples > 1 else self.id)
        glViewport(0, 0, self.width, self.height)
        if self.use_color:
            glDrawBuffers(1, [GL_COLOR_ATTACHMENT0])
        else:
            glDrawBuffer(GL_NONE)
            glReadBuffer(GL_NONE)

    def read_depth_pixel(self, x, y):
        read_id = self.resolve_id if self.samples > 1 else self.id
        glBindFramebuffer(GL_READ_FRAMEBUFFER, read_id)
        depth_buffer = glReadPixels(int(x), int(y), 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)
        return depth_buffer[0][0]

    def delete(self):
        self.color_tex.delete()
        self.depth_tex.delete()
        if self.msaa_color_tex: self.msaa_color_tex.delete()
        if self.msaa_depth_tex: self.msaa_depth_tex.delete()

        fbo_ids = [fbo for fbo in (self.id, self.resolve_id) if fbo is not None]
        if fbo_ids:
            glDeleteFramebuffers(len(fbo_ids), fbo_ids)
            self.id = self.resolve_id = None
