import time

from OpenGL.GL import *


class App:
    def __init__(self):
        from ui.views.loading_view import LoadingCancelled
        try:
            from ui.platform.application_window import ApplicationWindow
            self.application_window = ApplicationWindow()

            self._configure_opengl()

            self.imgui_renderer = self._init_imgui()

            from ui.views.loading_view import LoadingView
            self.loading_view = LoadingView(self.application_window)
            from util.startup import set_checkpoint_handler
            set_checkpoint_handler(self.loading_view.service)

            self.scene = self._load_scene()
            self.loading_view.service()

            from rendering.textures.frame_buffer import FrameBuffer
            self.frame_buffer = FrameBuffer(*self.application_window.pixel_size(), samples=4)
            scale = self.application_window.scale()
            self.scene.camera.initialize(
                self.application_window.pixel_size(), (scale, scale)
            )

            self.loading_view.service()

            from input import Input
            self.input = Input(
                self.application_window.window,
                self.application_window.chrome,
                self.scene.camera,
                self.frame_buffer,
            )
            from service.camera_flight import CameraFlight
            camera_flight = CameraFlight(self.scene.camera)
            from scene_controller import SceneController
            self.scene_controller = SceneController(
                self.scene,
                self.frame_buffer,
                self.input,
                camera_flight,
            )
            from ui.ui_manager import UIManager
            self.ui_manager = UIManager(
                self.input,
                self.scene.camera,
                self.application_window.chrome,
                camera_flight,
                self.scene_controller.apply_graphics_config,
                self.scene_controller.weather_data_textures,
            )
            self.loading_view.service()

        except LoadingCancelled:
            from util.startup import clear_checkpoint_handler
            clear_checkpoint_handler()
            if hasattr(self, "loading_view"):
                self.loading_view.destroy()
            if hasattr(self, "imgui_renderer"):
                self.imgui_renderer.shutdown()
            if hasattr(self, "application_window"):
                self.application_window.destroy()
            raise SystemExit()

    def _configure_opengl(self):
        from util.config import config
        if config.opengl.debug:
            from util.gl_debug_messages import enable_gl_debug_messages
            enable_gl_debug_messages()

        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClearDepth(0.0)
        glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE)
        glClear(GL_COLOR_BUFFER_BIT)

        glEnable(GL_BLEND)
        glEnable(GL_MULTISAMPLE)
        glEnable(GL_PROGRAM_POINT_SIZE)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        glEnable(GL_PRIMITIVE_RESTART)
        from rendering.geometry.geometry_data import RESTART_INDEX
        glPrimitiveRestartIndex(RESTART_INDEX)

        from PIL import Image
        from rendering.textures.texture import Texture
        Image.MAX_IMAGE_PIXELS = 233_280_000
        Texture.MAX_TEXTURE_SIZE = glGetIntegerv(GL_MAX_TEXTURE_SIZE)

    def _init_imgui(self):
        from imgui_bundle import imgui, implot
        from ui.scaling import apply_imgui_scaling
        from ui.platform.sdl_imgui_backend import SDL3Renderer
        from util.paths import IMGUI_INI
        from util.theme import apply_theme

        imgui.create_context()
        implot.create_context()
        apply_theme()
        imgui.get_io().set_ini_filename(IMGUI_INI)

        renderer = SDL3Renderer(self.application_window.window)
        apply_imgui_scaling(self.application_window.scale())
        self.application_window.update_imgui_display_size()
        return renderer

    def _load_scene(self):
        from scene_builder import scene_builder
        from ui.views.loading_view import LoadingCancelled

        self.loading_view.show(0.0)
        builder = scene_builder()
        try:
            while True:
                self.loading_view.show(*next(builder))
        except StopIteration as result:
            return result.value
        except LoadingCancelled:
            builder.close()
            raise

    def _prepare_and_show_main_window(self):
        from imgui_bundle import imgui

        self.loading_view.show(1.0, "Starting...")
        self.scene_controller.update(0.0)

        pixel_size = self.application_window.pixel_size()
        scale = self.application_window.scale()
        self.frame_buffer.update_size(*pixel_size)
        self.scene.camera.initialize(pixel_size, (scale, scale))
        self.application_window.update_imgui_display_size()
        self.imgui_renderer.process_inputs()
        self.scene.render(self.frame_buffer)
        self.ui_manager.render(0.0, self.scene.camera)
        self.imgui_renderer.render(imgui.get_draw_data())
        self.application_window.swap()

        time.sleep(0.15)

        self.application_window.show()
        self.loading_view.destroy()
        self.application_window.raise_window()
        from util.startup import clear_checkpoint_handler
        clear_checkpoint_handler()

    def process_events(self):
        from ui.scaling import apply_imgui_scaling
        from sdl3 import SDL as sdl

        for event in self.application_window.poll_events():
            self.imgui_renderer.process_event(event)

            if event.type in (sdl.SDL_EVENT_QUIT, sdl.SDL_EVENT_WINDOW_CLOSE_REQUESTED):
                self.application_window.chrome.close()
            elif event.type == sdl.SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED:
                width, height = self.application_window.pixel_size()
                if width > 0 and height > 0:
                    self.scene.camera.set_viewport_size(width, height)
                    self.frame_buffer.update_size(width, height)
                    self.application_window.update_imgui_display_size()
            elif event.type == sdl.SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED:
                scale = self.application_window.scale()
                self.scene.camera.pixel_scale_x = scale
                self.scene.camera.pixel_scale_y = scale
                apply_imgui_scaling(scale)
                self.application_window.update_imgui_display_size()

            self.input.process_event(event)

    def run(self):
        from imgui_bundle import imgui
        from sdl3 import SDL as sdl
        import time

        self._prepare_and_show_main_window()

        last_frame = time.perf_counter()
        while not self.application_window.chrome.should_close:
            current_frame = time.perf_counter()
            delta_time = current_frame - last_frame
            last_frame = current_frame

            # --- Input ---
            self.process_events()
            self.imgui_renderer.process_inputs()
            self.application_window.update_imgui_display_size()

            if self.application_window.chrome.is_minimized:
                sdl.SDL_Delay(100)
                continue

            # --- Update ---
            self.scene_controller.update(delta_time)

            # --- Render ---
            self.scene.render(self.frame_buffer)

            # --- UI ---
            self.ui_manager.render(delta_time, self.scene.camera)
            self.imgui_renderer.render(imgui.get_draw_data())

            self.application_window.swap()

        self.exit()

    def exit(self):
        from model.state.view_state import view_state

        self.scene_controller.destroy()
        self.ui_manager.destroy()
        self.scene.delete()
        self.frame_buffer.delete()
        self.imgui_renderer.shutdown()
        self.application_window.destroy()

        view_state.save_enabled_views()
