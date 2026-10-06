from typing import override

from imgui_bundle import imgui

from ui.components.base_component import ViewModelComponent
from ui.viewmodels.render_settings_view_models import PowerPlantSettingsViewModel


class PowerPlantSettingsComponent(ViewModelComponent[PowerPlantSettingsViewModel]):
    """Controls the visibility and appearance of power-plant renderables."""

    def __init__(self, view_model: PowerPlantSettingsViewModel | None = None):
        super().__init__(view_model or PowerPlantSettingsViewModel())
        self.preferred_size = (400, 300)

    @override
    def render(self):
        vm = self.view_model
        self.prepare_render()
        for plant_type in vm.plant_types:
            self.checkbox_value(
                plant_type,
                vm.render_power_plants.get(plant_type, False),
                lambda value, plant_type=plant_type: vm.set_plant_visible(
                    plant_type, value,
                ),
            )
            imgui.same_line()
            self.color_edit_value(
                f"##{plant_type}_color",
                vm.power_plant_colors[plant_type],
                lambda value, plant_type=plant_type: vm.set_plant_color(
                    plant_type, value,
                ),
            )

        imgui.separator()
        self.checkbox_value(
            "Point",
            vm.render_power_plant_points,
            lambda value: vm.set_value("render_power_plant_points", value),
        )
        imgui.same_line()
        self.slider_float_value(
            "Size##point_size",
            vm.power_plant_point_size,
            2.0,
            64.0,
            lambda value: vm.set_value("power_plant_point_size", value),
            format="%.1f px",
        )
        self.checkbox_value(
            "Model",
            vm.render_power_plant_models,
            lambda value: vm.set_value("render_power_plant_models", value),
        )
        imgui.same_line()
        self.slider_float_value(
            "Size##model_size",
            vm.model_scale,
            0.0,
            4.0,
            lambda value: vm.set_value("model_scale", value),
            format="%.2f",
        )
