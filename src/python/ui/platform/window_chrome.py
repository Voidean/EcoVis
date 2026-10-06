import ctypes

from sdl3 import SDL as sdl


class WindowChrome:
    RESIZE_BORDER = 6.0

    def __init__(self, window):
        self.window = window
        self.should_close = False
        self.resize_enabled = True
        self.drag_left = 0.0
        self.drag_right = 0.0
        self.drag_height = 0.0
        self._hit_test_callback = sdl.SDL_HitTest(self._hit_test)

        if not sdl.SDL_SetWindowHitTest(
            self.window, self._hit_test_callback, None
        ):
            error = sdl.SDL_GetError().decode("utf-8")
            raise RuntimeError(f"SDL could not install window hit testing: {error}")

    def set_title_bar_drag_region(self, left, right, height):
        self.drag_left = left
        self.drag_right = right
        self.drag_height = height

    def set_resize_enabled(self, enabled):
        self.resize_enabled = enabled

    def minimize(self):
        sdl.SDL_MinimizeWindow(self.window)

    def toggle_maximized(self):
        if self.is_fullscreen:
            self.toggle_fullscreen()
        if self.is_maximized:
            sdl.SDL_RestoreWindow(self.window)
        else:
            sdl.SDL_MaximizeWindow(self.window)

    def close(self):
        self.should_close = True

    def toggle_fullscreen(self):
        sdl.SDL_SetWindowFullscreen(self.window, not self.is_fullscreen)

    @property
    def is_maximized(self):
        return bool(sdl.SDL_GetWindowFlags(self.window) & sdl.SDL_WINDOW_MAXIMIZED)

    @property
    def is_minimized(self):
        return bool(sdl.SDL_GetWindowFlags(self.window) & sdl.SDL_WINDOW_MINIMIZED)

    @property
    def is_fullscreen(self):
        return bool(sdl.SDL_GetWindowFlags(self.window) & sdl.SDL_WINDOW_FULLSCREEN)

    def _hit_test(self, _window, point, _callback_data):
        x = point.contents.x
        y = point.contents.y
        width, height = self._window_size()

        if self.resize_enabled and not self.is_maximized and not self.is_fullscreen:
            border = self.RESIZE_BORDER
            left = x < border
            right = x >= width - border
            top = y < border
            bottom = y >= height - border

            if top and left:
                return sdl.SDL_HITTEST_RESIZE_TOPLEFT
            if top and right:
                return sdl.SDL_HITTEST_RESIZE_TOPRIGHT
            if bottom and left:
                return sdl.SDL_HITTEST_RESIZE_BOTTOMLEFT
            if bottom and right:
                return sdl.SDL_HITTEST_RESIZE_BOTTOMRIGHT
            if left:
                return sdl.SDL_HITTEST_RESIZE_LEFT
            if right:
                return sdl.SDL_HITTEST_RESIZE_RIGHT
            if top:
                return sdl.SDL_HITTEST_RESIZE_TOP
            if bottom:
                return sdl.SDL_HITTEST_RESIZE_BOTTOM

        if (
            self.drag_left <= x < self.drag_right
            and 0 <= y < self.drag_height
            and not self.is_fullscreen
        ):
            return sdl.SDL_HITTEST_DRAGGABLE

        return sdl.SDL_HITTEST_NORMAL

    def _window_size(self):
        width = ctypes.c_int()
        height = ctypes.c_int()
        sdl.SDL_GetWindowSize(
            self.window, ctypes.byref(width), ctypes.byref(height)
        )
        return width.value, height.value

    def destroy(self):
        sdl.SDL_SetWindowHitTest(self.window, sdl.SDL_HitTest(), None)
        self._hit_test_callback = None
