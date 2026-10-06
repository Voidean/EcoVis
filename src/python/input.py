import math

from imgui_bundle import imgui
from OpenGL.GL import *
from sdl3 import SDL as sdl

from ui.interactions.interaction_manager import interaction_manager
from ui.interactions.interaction_event import KeyEvent, MouseEvent
from util.config import config
from util.input_constants import KEY_ESCAPE, MouseButton
from util.screen_projection import screen_space_to_world_space

DRAG_THRESHOLD = 5  # pixels


class Input:
    def __init__(self, window, window_chrome, camera, frame_buffer):
        self.window = window
        self.window_chrome = window_chrome
        self.frame_buffer = frame_buffer
        self.camera = camera

        self.keys_down = set()
        self.keys_pressed = set()
        self.scroll_delta = 0
        self.mouse_pos = 0, 0

        self.drag_button = None
        self.drag_start_pos = None
        self.drag_last_pos = None
        self.drag_delta = 0, 0

    def process_event(self, event):
        io = imgui.get_io()

        if event.type in (sdl.SDL_EVENT_KEY_DOWN, sdl.SDL_EVENT_KEY_UP):
            self._handle_key_event(event, io.want_capture_keyboard)
        elif event.type in (
            sdl.SDL_EVENT_MOUSE_BUTTON_DOWN,
            sdl.SDL_EVENT_MOUSE_BUTTON_UP,
        ):
            self._handle_mouse_button_event(event, io.want_capture_mouse)
        elif event.type == sdl.SDL_EVENT_MOUSE_MOTION:
            self._handle_mouse_motion_event(event, io.want_capture_mouse)
        elif event.type == sdl.SDL_EVENT_MOUSE_WHEEL:
            if not io.want_capture_mouse:
                self.scroll_delta += event.wheel.y

    def _handle_key_event(self, event, captured):
        key = int(event.key.scancode)
        pressed = event.type == sdl.SDL_EVENT_KEY_DOWN

        if pressed:
            if not event.key.repeat:
                self.keys_pressed.add(key)
            if not captured:
                self.keys_down.add(key)
                if not event.key.repeat:
                    self.handle_key_press(key)
        else:
            self.keys_down.discard(key)

    def handle_key_press(self, key):
        if key == config.keybinds.toggle_fullscreen:
            self.window_chrome.toggle_fullscreen()

        if key == KEY_ESCAPE and self.window_chrome.is_fullscreen:
            self.window_chrome.toggle_fullscreen()

        if key == config.keybinds.toggle_wireframe:
            mode = glGetIntegerv(GL_POLYGON_MODE)
            if mode[0] == GL_FILL:
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            elif mode[0] == GL_LINE:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        interaction_manager.dispatch(KeyEvent(key))

    def _handle_mouse_button_event(self, event, captured):
        button = int(event.button.button)
        pressed = event.type == sdl.SDL_EVENT_MOUSE_BUTTON_DOWN

        if pressed:
            if captured or button not in (
                MouseButton.LEFT,
                MouseButton.MIDDLE,
                MouseButton.RIGHT,
            ):
                return
            self.drag_button = button
            position = float(event.button.x), float(event.button.y)
            self.drag_last_pos = self.drag_start_pos = position
            sdl.SDL_SetWindowRelativeMouseMode(self.window, True)
            return

        if self.drag_button != button:
            return

        if self.is_click():
            world_pos = screen_space_to_world_space(
                self.drag_last_pos, self.camera, self.frame_buffer
            )
            if world_pos:
                interaction_manager.dispatch(
                    MouseEvent(
                        button,
                        self.drag_last_pos,
                        world_pos,
                    )
                )

        sdl.SDL_SetWindowRelativeMouseMode(self.window, False)
        self.drag_button = None
        self.drag_last_pos = None

    def _handle_mouse_motion_event(self, event, captured):
        if self.drag_button is not None:
            delta_x = float(event.motion.xrel)
            delta_y = float(event.motion.yrel)
            old_delta_x, old_delta_y = self.drag_delta
            self.drag_delta = old_delta_x + delta_x, old_delta_y + delta_y

            last_x, last_y = self.drag_last_pos
            self.drag_last_pos = last_x + delta_x, last_y + delta_y
            self.mouse_pos = self.drag_start_pos
        elif not captured:
            self.mouse_pos = float(event.motion.x), float(event.motion.y)

    def is_click(self):
        start_x, start_y = self.drag_start_pos
        end_x, end_y = self.drag_last_pos
        return math.hypot(end_x - start_x, end_y - start_y) < DRAG_THRESHOLD
