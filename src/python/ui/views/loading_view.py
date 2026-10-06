from OpenGL.GL import *
from imgui_bundle import imgui
from sdl3 import SDL as sdl

from ui.viewmodels.loading_view_model import LoadingViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata
from util.config import config

LOADING_WINDOW_SIZE = (440, 150)
TITLE_BAR_HEIGHT = 34.0
CAPTION_BUTTON_WIDTH = 46.0


class LoadingCancelled(Exception):
    pass


class LoadingView(View[LoadingViewModel]):
    """Independent splash window with its own GL and ImGui contexts."""

    def __init__(
            self,
            application_window,
            view_model: LoadingViewModel | None = None,
    ):
        super().__init__(
            ViewMetadata(ViewId.LOADING, "Loading"),
            view_model or LoadingViewModel(),
        )
        self.application_window = application_window
        self.main_imgui_context = imgui.get_current_context()
        self._destroyed = False

        flags = (
            sdl.SDL_WINDOW_OPENGL
            | sdl.SDL_WINDOW_BORDERLESS
            | sdl.SDL_WINDOW_HIGH_PIXEL_DENSITY
            | sdl.SDL_WINDOW_HIDDEN
        )
        self.window = sdl.SDL_CreateWindow(
            config.window.title.encode("utf-8"),
            LOADING_WINDOW_SIZE[0],
            LOADING_WINDOW_SIZE[1],
            flags,
        )
        if not self.window:
            raise RuntimeError(
                f"SDL loading window creation failed: "
                f"{application_window.sdl_error()}"
            )

        self.gl_context = sdl.SDL_GL_CreateContext(self.window)
        if not self.gl_context:
            sdl.SDL_DestroyWindow(self.window)
            raise RuntimeError(
                f"SDL loading context creation failed: "
                f"{application_window.sdl_error()}"
            )

        from ui.platform.window_chrome import WindowChrome

        self.chrome = WindowChrome(self.window)
        self.chrome.set_resize_enabled(False)

        self._activate()
        self.imgui_context = imgui.create_context()
        imgui.set_current_context(self.imgui_context)
        from util.theme import apply_imgui_theme
        apply_imgui_theme()
        imgui.get_io().set_ini_filename(None)

        from ui.scaling import apply_imgui_scaling
        from ui.platform.sdl_imgui_backend import SDL3Renderer

        self.imgui_renderer = SDL3Renderer(self.window)
        apply_imgui_scaling(self._scale())
        self._update_display_size()

        glClearColor(0.03, 0.03, 0.05, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        self._swap()

        sdl.SDL_SetWindowPosition(
            self.window, sdl.SDL_WINDOWPOS_CENTERED, sdl.SDL_WINDOWPOS_CENTERED
        )
        sdl.SDL_SetWindowAlwaysOnTop(self.window, True)
        sdl.SDL_ShowWindow(self.window)
        sdl.SDL_RaiseWindow(self.window)
        sdl.SDL_SyncWindow(self.window)
        self._restore_main()

    def show(self, progress, text="Loading..."):
        self.view_model.update(progress=progress, text=text)
        self.service(force_render=True)

    def service(self, force_render=False):
        self._activate()
        imgui.set_current_context(self.imgui_context)
        try:
            self._process_events()

            if not self.view_model.should_render(force_render):
                return
            self.imgui_renderer.process_inputs()
            self._update_display_size()

            pixel_width, pixel_height = self._pixel_size()
            glViewport(0, 0, pixel_width, pixel_height)
            glClear(GL_COLOR_BUFFER_BIT)

            close_clicked = self.render()
            self.imgui_renderer.render(imgui.get_draw_data())
            self._swap()

            if close_clicked:
                self.chrome.close()
                raise LoadingCancelled()
        finally:
            self._restore_main()

    def _process_events(self):
        event = sdl.SDL_Event()
        while sdl.SDL_PollEvent(ctypes.byref(event)):
            self.imgui_renderer.process_event(event)
            if event.type in (
                sdl.SDL_EVENT_QUIT,
                sdl.SDL_EVENT_WINDOW_CLOSE_REQUESTED,
            ):
                self.chrome.close()
            elif event.type in (
                sdl.SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED,
                sdl.SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,
            ):
                self._update_display_size()

        if self.chrome.should_close:
            raise LoadingCancelled()

    def _activate(self):
        if not sdl.SDL_GL_MakeCurrent(self.window, self.gl_context):
            raise RuntimeError(
                f"Could not activate loading context: "
                f"{self.application_window.sdl_error()}"
            )

    def _restore_main(self):
        imgui.set_current_context(self.main_imgui_context)
        if not sdl.SDL_GL_MakeCurrent(
            self.application_window.window,
            self.application_window.gl_context,
        ):
            raise RuntimeError(
                f"Could not restore main context: "
                f"{self.application_window.sdl_error()}"
            )

    def _update_display_size(self):
        logical_width, logical_height = self._size()
        pixel_width, pixel_height = self._pixel_size()
        io = imgui.get_io()
        io.display_size = (float(logical_width), float(logical_height))
        if logical_width > 0 and logical_height > 0:
            io.display_framebuffer_scale = (
                float(pixel_width) / float(logical_width),
                float(pixel_height) / float(logical_height),
            )

    def _size(self):
        width = ctypes.c_int()
        height = ctypes.c_int()
        if not sdl.SDL_GetWindowSize(
            self.window, ctypes.byref(width), ctypes.byref(height)
        ):
            raise RuntimeError(
                f"Could not read loading window size: "
                f"{self.application_window.sdl_error()}"
            )
        return width.value, height.value

    def _pixel_size(self):
        width = ctypes.c_int()
        height = ctypes.c_int()
        if not sdl.SDL_GetWindowSizeInPixels(
            self.window, ctypes.byref(width), ctypes.byref(height)
        ):
            raise RuntimeError(
                f"Could not read loading pixel size: "
                f"{self.application_window.sdl_error()}"
            )
        return width.value, height.value

    def _scale(self):
        return max(1.0, float(sdl.SDL_GetWindowDisplayScale(self.window)))

    def _swap(self):
        sdl.SDL_GL_SwapWindow(self.window)

    def render(self, dt=0.0):
        self.prepare_render()
        imgui.new_frame()

        io = imgui.get_io()
        width = io.display_size.x
        height = io.display_size.y
        imgui.set_next_window_pos((0.0, 0.0))
        imgui.set_next_window_size((width, height))

        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_bring_to_front_on_focus
        )
        imgui.begin("Loading", flags=flags)

        imgui.set_cursor_screen_pos((12.0, 8.0))
        imgui.text(config.window.title)

        close_x = max(0.0, width - CAPTION_BUTTON_WIDTH)
        imgui.set_cursor_screen_pos((close_x, 0.0))
        close_clicked = imgui.invisible_button(
            "##loading_close", (CAPTION_BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        )
        self._draw_close_button()

        self.chrome.set_title_bar_drag_region(
            0.0, close_x, TITLE_BAR_HEIGHT
        )

        content_width = max(1.0, width - 32.0)
        imgui.set_cursor_screen_pos((16.0, TITLE_BAR_HEIGHT + 16.0))
        imgui.text(self.view_model.text)
        imgui.spacing()
        imgui.progress_bar(
            self.view_model.progress,
            size_arg=(content_width, 0.0),
        )
        imgui.spacing()
        imgui.text_disabled(f"{self.view_model.progress_percent} %")

        imgui.end()
        imgui.render()
        return close_clicked

    @staticmethod
    def _draw_close_button():
        hovered = imgui.is_item_hovered()
        active = imgui.is_item_active()
        item_min = imgui.get_item_rect_min()
        item_max = imgui.get_item_rect_max()
        draw_list = imgui.get_window_draw_list()

        if hovered or active:
            color = (
                (0.78, 0.15, 0.15, 1.0)
                if active
                else (0.91, 0.18, 0.18, 1.0)
            )
            draw_list.add_rect_filled(
                item_min, item_max, imgui.get_color_u32(color)
            )

        center_x = (item_min.x + item_max.x) * 0.5
        center_y = (item_min.y + item_max.y) * 0.5
        icon_color = imgui.get_color_u32(imgui.Col_.text)
        draw_list.add_line(
            (center_x - 5.0, center_y - 5.0),
            (center_x + 5.0, center_y + 5.0),
            icon_color,
            1.25,
        )
        draw_list.add_line(
            (center_x + 5.0, center_y - 5.0),
            (center_x - 5.0, center_y + 5.0),
            icon_color,
            1.25,
        )

    def destroy(self):
        if self._destroyed:
            return

        self._activate()
        imgui.set_current_context(self.imgui_context)
        self.imgui_renderer.shutdown()
        imgui.destroy_context(self.imgui_context)

        self._restore_main()
        self.chrome.destroy()
        sdl.SDL_GL_DestroyContext(self.gl_context)
        sdl.SDL_DestroyWindow(self.window)
        View.destroy(self)
        self._destroyed = True
