from collections.abc import Callable

from input import Input
from ui.view_model import ViewModel
from util.config import ConfigChanges, config
from util.input_constants import KEY_ESCAPE


PREVIEWED_GRAPHICS_SETTINGS = {
    "graphics.msaa_enabled",
    "graphics.ambient",
    "graphics.shadow_map_resolution",
    "graphics.shadow_cascade_count",
}


class ConfigViewModel(ViewModel):
    """Owns staged configuration edits and their preview/save lifecycle."""

    def __init__(
            self,
            input_state: Input,
            graphics_preview_handler: Callable | None = None,
    ):
        super().__init__()
        self.input = input_state
        self.unsaved_settings = ConfigChanges()
        self.waiting_for_key = None
        self.graphics_preview_handler = graphics_preview_handler

    @property
    def has_unsaved_changes(self) -> bool:
        return any(
            config.get(path) != value
            for path, value in self._leaf_values(
                self.unsaved_settings.values
            )
        )

    @property
    def keybind_actions(self) -> tuple[str, ...]:
        return tuple(config.keybinds.__dict__)

    def tick(self):
        if self.destroyed or not self.waiting_for_key or not self.input.keys_pressed:
            return
        active_key = self.input.keys_pressed.pop()
        if active_key != KEY_ESCAPE:
            self.set_setting(
                f"keybinds.{self.waiting_for_key}",
                active_key,
            )
        self.waiting_for_key = None

    def value(self, path: str):
        return self.unsaved_settings.get(path, config.get(path))

    @staticmethod
    def original_value(path: str):
        return config.get(path)

    @staticmethod
    def default_value(path: str):
        return config.get_default(path)

    def is_modified(self, path: str) -> bool:
        return self.value(path) != self.original_value(path)

    def set_setting(self, path: str, value):
        self.unsaved_settings.set(path, value)
        if path in PREVIEWED_GRAPHICS_SETTINGS:
            self.preview_graphics()

    def reset_setting(self, path: str):
        default = self.default_value(path)
        if default is not None:
            self.set_setting(path, default)

    def begin_key_capture(self, action):
        self.waiting_for_key = action

    def cancel_key_capture(self):
        self.waiting_for_key = None

    def restore_all_defaults(self):
        self.unsaved_settings.restore_all_defaults()
        self.preview_graphics()

    def discard(self):
        self.unsaved_settings.clear()
        self.reset_graphics_preview()
        self.waiting_for_key = None

    def save(self):
        if self.unsaved_settings.values:
            config.save(self.unsaved_settings.values)
            self.unsaved_settings.clear()
        self.reset_graphics_preview()
        self.waiting_for_key = None

    def preview_graphics(self):
        if self.graphics_preview_handler:
            self.graphics_preview_handler(self.unsaved_settings)

    def reset_graphics_preview(self):
        if self.graphics_preview_handler:
            self.graphics_preview_handler()

    def hide(self):
        if self.unsaved_settings.values:
            self.discard()
        else:
            self.waiting_for_key = None

    def destroy(self):
        if self.destroyed:
            return
        self.hide()
        super().destroy()

    @staticmethod
    def _leaf_values(values, prefix=""):
        for key, value in values.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                yield from ConfigViewModel._leaf_values(value, path)
            else:
                yield path, value
