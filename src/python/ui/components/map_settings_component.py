from typing import override

from imgui_bundle import imgui

from ui.components.base_component import ViewModelComponent
from ui.viewmodels.render_settings_view_models import MapSettingsViewModel


class MapSettingsComponent(ViewModelComponent[MapSettingsViewModel]):
    def __init__(self, view_model: MapSettingsViewModel | None = None):
        super().__init__(view_model or MapSettingsViewModel())
        self.preferred_size = (400, 300)

    @override
    def render(self):
        vm = self.view_model
        self.prepare_render()
        self._combo_control(
            "Projection", vm.projections, vm.projection, vm.set_projection,
        )
        self.slider_float_value(
            "Vertical scale", vm.vertical_scale, 1.0, 20.0,
            lambda value: vm.set_value("vertical_scale", value),
            format="%.1f",
        )

        imgui.separator()

        self.checkbox_value(
            "Clouds", vm.render_clouds,
            lambda value: vm.set_value("render_clouds", value),
        )
        self.checkbox_value(
            "Atmosphere", vm.render_atmosphere,
            lambda value: vm.set_value("render_atmosphere", value),
        )
        self.checkbox_value(
            "Shadows", vm.render_shadows,
            lambda value: vm.set_value("render_shadows", value),
        )

        imgui.separator()

        self.checkbox_value(
            "Power grid", vm.render_power_grid,
            lambda value: vm.set_value("render_power_grid", value),
        )
        self.color_edit_value(
            "Power grid colour", vm.power_grid_color,
            lambda value: vm.set_value("power_grid_color", value),
        )

        imgui.separator()

        self.checkbox_value(
            "Coastlines", vm.render_coastlines,
            lambda value: vm.set_value("render_coastlines", value),
        )
        self.checkbox_value(
            "Borders", vm.render_borders,
            lambda value: vm.set_value("render_borders", value),
        )
        self.color_edit_value(
            "Colour", vm.border_color,
            lambda value: vm.set_value("border_color", value),
        )
