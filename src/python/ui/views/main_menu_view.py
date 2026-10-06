from imgui_bundle import imgui

from service.camera_flight import CameraFlight
from ui.views.help_view import HelpView
from ui.components.location_search_component import LocationSearchComponent
from ui.components.map_settings_component import MapSettingsComponent
from ui.components.power_plant_settings_component import PowerPlantSettingsComponent
from ui.viewmodels.main_menu_view_model import MainMenuViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class MainMenuView(View[MainMenuViewModel]):
    CAPTION_BUTTON_WIDTH = 46.0
    EXTRA_VERTICAL_PADDING = 3.0

    def __init__(
            self,
            window_chrome,
            view_model: MainMenuViewModel,
            camera_flight: CameraFlight,
    ):
        super().__init__(
            ViewMetadata(ViewId.MAIN_MENU_BAR, "Main Menu"),
            view_model,
        )
        self.window_chrome = window_chrome
        self.location_search = LocationSearchComponent(camera_flight)
        self.map_settings = MapSettingsComponent()
        self.power_plant_settings = PowerPlantSettingsComponent()
        self.help_view = HelpView()

    def render(self, dt, camera):
        self.prepare_render()
        vm = self.view_model
        style = imgui.get_style()
        imgui.push_style_var(
            imgui.StyleVar_.frame_padding,
            (style.frame_padding.x, style.frame_padding.y + self.EXTRA_VERTICAL_PADDING),
        )

        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("Windows"):
                for view_id, title, enabled in vm.view_options:
                    changed, new_value = imgui.checkbox(title, enabled)
                    if changed:
                        vm.set_view_enabled(view_id, new_value)

                self.checkbox_value(
                    "LOD Debug",
                    vm.view_enabled(ViewId.DEBUG),
                    lambda value: vm.set_view_enabled(ViewId.DEBUG, value),
                )  # TODO remove once out of dev

                imgui.end_menu()

            self._render_component_menu("Map Settings", self.map_settings)
            self._render_component_menu("Power plants Settings", self.power_plant_settings)

            if imgui.button("Reset Camera"):
                vm.reset_camera()

            if imgui.button("Config"):
                vm.open_view(ViewId.CONFIG)

            if imgui.begin_menu("Help"):
                if imgui.menu_item_simple("UI guide..."):
                    self.help_view.view_model.open()
                imgui.end_menu()

            imgui.same_line(600)
            search_end = self.location_search.render(camera)

            self._render_window_chrome(search_end.x)

            imgui.end_main_menu_bar()

        imgui.pop_style_var()
        self.help_view.render(dt)

    @staticmethod
    def _render_component_menu(label, component):
        preferred_width = component.preferred_size[0]
        imgui.set_next_window_size_constraints(
            (preferred_width, 0.0),
            (preferred_width, imgui.get_io().display_size.y),
        )
        if imgui.begin_menu(label):
            component.render()
            imgui.end_menu()

    def _render_window_chrome(self, content_end_x):
        bar_pos = imgui.get_window_pos()
        bar_width = imgui.get_window_width()
        bar_height = imgui.get_window_height()
        buttons_width = self.CAPTION_BUTTON_WIDTH * 3
        buttons_start_x = bar_pos.x + bar_width - buttons_width

        drag_start_x = content_end_x + imgui.get_style().item_spacing.x
        self.window_chrome.set_title_bar_drag_region(
            drag_start_x - bar_pos.x,
            max(drag_start_x, buttons_start_x) - bar_pos.x,
            bar_height,
        )

        actions = (
            ("minimize", self.window_chrome.minimize),
            ("maximize", self.window_chrome.toggle_maximized),
            ("close", self.window_chrome.close),
        )
        for index, (name, action) in enumerate(actions):
            button_x = buttons_start_x + index * self.CAPTION_BUTTON_WIDTH
            self._caption_button(name, button_x, bar_pos.y, bar_height, action)

    def _caption_button(self, name, x, y, height, action):
        imgui.set_cursor_screen_pos((x, y))
        clicked = imgui.invisible_button(
            f"##window_{name}", (self.CAPTION_BUTTON_WIDTH, height)
        )
        hovered = imgui.is_item_hovered()
        active = imgui.is_item_active()

        item_min = imgui.get_item_rect_min()
        item_max = imgui.get_item_rect_max()
        draw_list = imgui.get_window_draw_list()

        if hovered or active:
            if name == "close":
                color = (0.78, 0.15, 0.15, 1.0) if active else (0.91, 0.18, 0.18, 1.0)
                background_color = imgui.get_color_u32(color)
            else:
                color_id = imgui.Col_.button_active if active else imgui.Col_.button_hovered
                background_color = imgui.get_color_u32(color_id)
            draw_list.add_rect_filled(item_min, item_max, background_color)
        else:
            background_color = imgui.get_color_u32(imgui.Col_.menu_bar_bg)

        center_x = (item_min.x + item_max.x) / 2.0
        center_y = (item_min.y + item_max.y) / 2.0
        icon_color = imgui.get_color_u32(imgui.Col_.text)
        self._draw_caption_icon(draw_list, name, center_x, center_y, icon_color, background_color)

        if clicked:
            action()

    def _draw_caption_icon(self, draw_list, name, center_x, center_y, color, bg_color):
        if name == "minimize":
            draw_list.add_line(
                (center_x - 6.0, center_y + 3.0),
                (center_x + 6.0, center_y + 3.0),
                color,
                1.25,
            )
        elif name == "maximize":
            if self.window_chrome.is_maximized:
                draw_list.add_rect(
                    (center_x - 4.0, center_y - 5.0),
                    (center_x + 6.0, center_y + 5.0),
                    color,
                )
                draw_list.add_rect_filled(
                    (center_x - 6.0, center_y - 3.0),
                    (center_x + 4.0, center_y + 7.0),
                    bg_color,
                )
                draw_list.add_rect(
                    (center_x - 6.0, center_y - 3.0),
                    (center_x + 4.0, center_y + 7.0),
                    color,
                )
            else:
                draw_list.add_rect(
                    (center_x - 6.0, center_y - 5.0),
                    (center_x + 6.0, center_y + 6.0),
                    color,
                )
        else:
            draw_list.add_line(
                (center_x - 5.0, center_y - 5.0),
                (center_x + 5.0, center_y + 5.0),
                color,
                1.25,
            )
            draw_list.add_line(
                (center_x + 5.0, center_y - 5.0),
                (center_x - 5.0, center_y + 5.0),
                color,
                1.25,
            )

    def destroy(self):
        self.help_view.destroy()
        self.location_search.destroy()
        self.map_settings.destroy()
        self.power_plant_settings.destroy()
        super().destroy()
