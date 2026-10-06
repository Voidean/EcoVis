from imgui_bundle import imgui

from collections.abc import Callable

from input import Input
from rendering.scene.directional_light import MAX_SHADOW_CASCADES
from ui.components.base_component import ViewModelComponent
from ui.viewmodels.config_view_model import ConfigViewModel
from util.input_constants import scancode_display_name

LABEL_WIDTH = 200
RESET_BUTTON_WIDTH = 25
RIGHT_PADDING = 30
UNSAVED_TEXT_COLOR = (1.0, 1.0, 0.5, 1.0)
WAITING_BUTTON_COLORS = (
    (0.2, 0.6, 1.0, 1.0),  # button
    (0.3, 0.7, 1.0, 1.0),  # hovered
    (0.1, 0.5, 0.9, 1.0),  # active
)


class ConfigComponent(ViewModelComponent[ConfigViewModel]):
    def __init__(
            self,
            input: Input,
            graphics_preview_handler: Callable | None = None,
            view_model: ConfigViewModel | None = None,
    ):
        super().__init__(
            view_model
            or ConfigViewModel(input, graphics_preview_handler)
        )
        self.preferred_size = (550, 550)

    def render(self):
        vm = self.view_model
        if vm.waiting_for_key and (
                imgui.is_mouse_clicked(imgui.MouseButton_.left)
                or imgui.is_mouse_clicked(imgui.MouseButton_.right)
        ):
            vm.cancel_key_capture()
        self.prepare_render()

        imgui.text("Some of these changes may require a restart to be applied!")

        imgui.separator()

        # ----------------------------------------------------------------
        # WINDOW SETTINGS
        # ----------------------------------------------------------------
        imgui.text_disabled("WINDOW SETTINGS")
        imgui.spacing()

        self._draw_setting("window.title", "Window Title")
        self._draw_setting("window.width", "Default Width")
        self._draw_setting("window.height", "Default Height")
        self._draw_setting("window.enable_ui_scaling", "Enable UI Scaling")
        self._draw_setting("window.show_fps", "Show FPS")
        self._draw_setting(
            "theme",
            "Theme (restart required)",
            options=("light", "dark"),
        )
        self._draw_setting(
            "data_windows.save_contents",
            "Save Data Window Contents",
        )

        imgui.separator()

        # ----------------------------------------------------------------
        # GRAPHICS
        # ----------------------------------------------------------------
        imgui.text_disabled("GRAPHICS SETTINGS")
        imgui.spacing()

        self._draw_setting("graphics.default_fov", "Default FOV", min_val=10.0, max_val=120.0, format_str="%.1f")
        self._draw_setting("graphics.tile_gpu_cache_size", "Map VRAM Cache Size", min_val=256, max_val=2048)
        self._draw_setting("graphics.msaa_enabled", "MSAA")
        self._draw_setting("graphics.ambient", "Ambient", min_val=0.0, max_val=1.0, format_str="%.2f",
                           speed=0.01)
        self._draw_setting("graphics.shadow_map_resolution", "Shadow Resolution", min_val=512, max_val=4096,
                           power_of_two=True)
        self._draw_setting("graphics.shadow_cascade_count", "Shadow Cascades", min_val=0,
                           max_val=MAX_SHADOW_CASCADES)

        imgui.separator()

        # ----------------------------------------------------------------
        # CONTROLS & INPUT
        # ----------------------------------------------------------------
        imgui.text_disabled("CONTROLS & INPUT SENSITIVITIES")
        imgui.spacing()

        self._draw_setting("input.key_step_size", "Key Step Size", min_val=0.05, max_val=10.0, format_str="%.2f",
                           speed=0.05)
        self._draw_setting("input.mouse_sensitivity", "Mouse Sensitivity", min_val=0.0001, max_val=0.05,
                           format_str="%.4f", speed=0.0001)
        self._draw_setting("input.scroll_speed", "Scroll Speed", min_val=0.05, max_val=2.0, format_str="%.2f",
                           speed=0.01)

        imgui.separator()

        # ----------------------------------------------------------------
        # KEYBINDS
        # ----------------------------------------------------------------
        imgui.text_disabled("KEYBINDS")
        imgui.spacing()

        for action in vm.keybind_actions:
            self._draw_key_setting(action)

        imgui.separator()
        imgui.spacing()

        # Final Actions (Save / Restore / Discard)
        if imgui.button("Restore All Defaults"):
            vm.restore_all_defaults()

        if vm.has_unsaved_changes:
            imgui.same_line()
            if imgui.button("Discard Changes"):
                vm.discard()

            imgui.same_line()
            if imgui.button("Save Settings", (-1, 0)):
                vm.save()

    def _draw_key_setting(self, action):
        vm = self.view_model
        path = f"keybinds.{action}"
        current_val = vm.value(path)
        is_unsaved = vm.is_modified(path)
        is_waiting = vm.waiting_for_key == action

        label = (str(action).replace("_", " ").title())

        if is_unsaved:
            imgui.push_style_color(imgui.Col_.text, UNSAVED_TEXT_COLOR)

        imgui.align_text_to_frame_padding()
        imgui.text(label)

        imgui.same_line(LABEL_WIDTH)

        window_width = imgui.get_window_width()
        widget_width = window_width - LABEL_WIDTH - RESET_BUTTON_WIDTH - RIGHT_PADDING

        imgui.push_item_width(widget_width)

        # Key Button
        display_key = scancode_display_name(current_val)
        label = f"Press key...##{action}" if is_waiting else f"{display_key}##{action}"

        if is_waiting:
            for color_id, color in zip(
                    (
                        imgui.Col_.button,
                        imgui.Col_.button_hovered,
                        imgui.Col_.button_active,
                    ),
                    WAITING_BUTTON_COLORS,
            ):
                imgui.push_style_color(color_id, color)

        if imgui.button(label, (widget_width, 0)):
            vm.begin_key_capture(action)

        if is_waiting:
            imgui.pop_style_color(3)
        if is_unsaved:
            imgui.pop_style_color()

        imgui.pop_item_width()

        imgui.same_line(window_width - RESET_BUTTON_WIDTH - RIGHT_PADDING / 2)
        if imgui.button(f"R##reset_{action}", (RESET_BUTTON_WIDTH, 0)):
            vm.reset_setting(path)

        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "Reset to default: "
                f"{scancode_display_name(vm.default_value(path))}"
            )

    def _draw_setting(self, path: str, label: str, min_val=None, max_val=None, format_str=None, speed=1.0,
                      power_of_two=False, options=None):
        vm = self.view_model
        current_val = vm.value(path)

        is_unsaved = vm.is_modified(path)
        changed = False
        new_val = current_val

        if is_unsaved:
            imgui.push_style_color(imgui.Col_.text, UNSAVED_TEXT_COLOR)

        imgui.align_text_to_frame_padding()
        imgui.text(label)

        imgui.same_line(LABEL_WIDTH)

        window_width = imgui.get_window_width()
        widget_width = window_width - LABEL_WIDTH - RESET_BUTTON_WIDTH - RIGHT_PADDING

        imgui.push_item_width(widget_width)

        if isinstance(current_val, bool):
            changed, new_val = imgui.checkbox(f"##{path}", current_val)
        elif isinstance(current_val, int):
            if min_val is not None and max_val is not None:
                if power_of_two:
                    min_power = int(min_val).bit_length() - 1
                    max_power = int(max_val).bit_length() - 1
                    current_power = max(min_power, min(max_power, current_val.bit_length() - 1))
                    changed, new_power = imgui.slider_int(
                        f"##{path}", current_power, min_power, max_power, format=f"{current_val}"
                    )
                    new_val = 2 ** new_power
                else:
                    changed, new_val = imgui.slider_int(f"##{path}", current_val, int(min_val), int(max_val))
            else:
                changed, new_val = imgui.input_int(f"##{path}", current_val)
        elif isinstance(current_val, float):
            fmt = format_str or "%.3f"
            if min_val is not None and max_val is not None:
                changed, new_val = imgui.slider_float(f"##{path}", current_val, float(min_val), float(max_val), fmt)
            else:
                changed, new_val = imgui.drag_float(f"##{path}", current_val, speed, min_val or 0.0, max_val or 0.0,
                                                    fmt)
        elif isinstance(current_val, str):
            if options is None:
                changed, new_val = imgui.input_text(f"##{path}", current_val)
            elif imgui.begin_combo(f"##{path}", current_val):
                for option in options:
                    selected = option == current_val
                    if imgui.selectable(option, selected)[0]:
                        changed, new_val = True, option
                    if selected:
                        imgui.set_item_default_focus()
                imgui.end_combo()

        if is_unsaved:
            imgui.pop_style_color()

        imgui.pop_item_width()

        imgui.same_line(window_width - RESET_BUTTON_WIDTH - RIGHT_PADDING / 2)
        if imgui.button(f"R##reset_{path}", (RESET_BUTTON_WIDTH, 0)):
            default_val = vm.default_value(path)
            if default_val is not None:
                new_val = default_val
                changed = True

        if imgui.is_item_hovered():
            imgui.set_tooltip(f"Reset to default: {vm.default_value(path)}")

        if changed:
            vm.set_setting(path, new_val)

    def __str__(self):
        return "config"
