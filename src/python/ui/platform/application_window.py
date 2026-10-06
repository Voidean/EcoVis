import sys

from OpenGL.GL import *
from sdl3 import SDL as sdl


class ApplicationWindow:
    def __init__(self):
        self._destroyed = False
        self.window, self.gl_context = self._create_sdl_window()

        from ui.platform.window_chrome import WindowChrome

        self.chrome = WindowChrome(self.window)
        self.chrome.set_resize_enabled(True)
        sdl.SDL_SetWindowPosition(
            self.window, sdl.SDL_WINDOWPOS_CENTERED, sdl.SDL_WINDOWPOS_CENTERED
        )
        sdl.SDL_MaximizeWindow(self.window)
        sdl.SDL_SyncWindow(self.window)

    @staticmethod
    def sdl_error():
        error = sdl.SDL_GetError()
        return error.decode("utf-8") if error else "Unknown SDL error"

    def _create_sdl_window(self):
        from util.config import config

        if not sdl.SDL_Init(sdl.SDL_INIT_VIDEO):
            raise RuntimeError(f"SDL initialization failed: {self.sdl_error()}")

        self._set_gl_attribute(sdl.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
        self._set_gl_attribute(sdl.SDL_GL_CONTEXT_MINOR_VERSION, 3)
        self._set_gl_attribute(sdl.SDL_GL_CONTEXT_PROFILE_MASK, sdl.SDL_GL_CONTEXT_PROFILE_CORE)
        self._set_gl_attribute(sdl.SDL_GL_DEPTH_SIZE, 24)

        context_flags = 0
        if config.opengl.debug:
            context_flags |= sdl.SDL_GL_CONTEXT_DEBUG_FLAG
        if sys.platform == "darwin":
            context_flags |= sdl.SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG
        if context_flags:
            self._set_gl_attribute(sdl.SDL_GL_CONTEXT_FLAGS, context_flags)

        flags = (
            sdl.SDL_WINDOW_OPENGL
            | sdl.SDL_WINDOW_BORDERLESS
            | sdl.SDL_WINDOW_RESIZABLE
            | sdl.SDL_WINDOW_HIGH_PIXEL_DENSITY
            | sdl.SDL_WINDOW_HIDDEN
        )
        window = sdl.SDL_CreateWindow(
            config.window.title.encode("utf-8"),
            config.window.width,
            config.window.height,
            flags,
        )
        if not window:
            sdl.SDL_Quit()
            raise RuntimeError(f"SDL window creation failed: {self.sdl_error()}")

        gl_context = sdl.SDL_GL_CreateContext(window)
        if not gl_context:
            sdl.SDL_DestroyWindow(window)
            sdl.SDL_Quit()
            raise RuntimeError(
                f"SDL OpenGL context creation failed: {self.sdl_error()}"
            )
        if not sdl.SDL_GL_MakeCurrent(window, gl_context):
            sdl.SDL_GL_DestroyContext(gl_context)
            sdl.SDL_DestroyWindow(window)
            sdl.SDL_Quit()
            raise RuntimeError(
                f"SDL could not activate the OpenGL context: {self.sdl_error()}"
            )

        return window, gl_context


    def _set_gl_attribute(self, attribute, value):
        if not sdl.SDL_GL_SetAttribute(attribute, value):
            raise RuntimeError(f"SDL could not set OpenGL attribute {attribute}: {self.sdl_error()}")

    def show(self):
        sdl.SDL_ShowWindow(self.window)
        sdl.SDL_MaximizeWindow(self.window)
        sdl.SDL_SyncWindow(self.window)

    def raise_window(self):
        sdl.SDL_RaiseWindow(self.window)

    def update_imgui_display_size(self):
        from imgui_bundle import imgui

        logical_width, logical_height = self.size()
        pixel_width, pixel_height = self.pixel_size()

        io = imgui.get_io()
        io.display_size = (float(logical_width), float(logical_height))
        if logical_width > 0 and logical_height > 0:
            io.display_framebuffer_scale = (
                float(pixel_width) / float(logical_width),
                float(pixel_height) / float(logical_height),
            )

    def poll_events(self):
        event = sdl.SDL_Event()
        while sdl.SDL_PollEvent(ctypes.byref(event)):
            yield event

    def size(self):
        width = ctypes.c_int()
        height = ctypes.c_int()
        if not sdl.SDL_GetWindowSize(
            self.window, ctypes.byref(width), ctypes.byref(height)
        ):
            raise RuntimeError(
                f"SDL could not read the window size: {self.sdl_error()}"
            )
        return width.value, height.value

    def pixel_size(self):
        width = ctypes.c_int()
        height = ctypes.c_int()
        if not sdl.SDL_GetWindowSizeInPixels(
            self.window, ctypes.byref(width), ctypes.byref(height)
        ):
            raise RuntimeError(
                f"SDL could not read the window pixel size: {self.sdl_error()}"
            )
        return width.value, height.value

    def scale(self):
        return max(1.0, float(sdl.SDL_GetWindowDisplayScale(self.window)))

    def swap(self):
        sdl.SDL_GL_SwapWindow(self.window)

    def destroy(self):
        if self._destroyed:
            return

        self.chrome.destroy()
        sdl.SDL_GL_DestroyContext(self.gl_context)
        sdl.SDL_DestroyWindow(self.window)
        sdl.SDL_Quit()
        self._destroyed = True
