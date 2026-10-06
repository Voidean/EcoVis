from typing import override

from imgui_bundle import imgui

from ui.components.base_component import ViewModelComponent
from ui.components.gradient_range_slider import gradient_range_slider
from ui.viewmodels.render_settings_view_models import MapWeatherControlViewModel


class MapWeatherControlComponent(ViewModelComponent[MapWeatherControlViewModel]):
    def __init__(self, view_model: MapWeatherControlViewModel | None = None):
        super().__init__(view_model or MapWeatherControlViewModel())

    @override
    def render(self):
        vm = self.view_model
        self.prepare_render()
        self.checkbox("render_data", "Data Overlay")

        self.combo("scalar_data_type", "Data Type##scalar", vm.scalar_data_types)
        scalar_heights = getattr(vm.scalar_data_type, "heights", None)
        if scalar_heights:
            self.combo(
                "scalar_height_type", "Data Height##scalar", scalar_heights,
            )

        self.combo("gradient", "Gradient", vm.gradients)

        if vm.displayed_scalar_type:
            edited_range = gradient_range_slider(
                vm.scale_start,
                vm.scale_end,
                "Gradient Clamping",
                vm.gradient,
                vm.displayed_scalar_type,
            )
            if edited_range is not None:
                vm.set_scale_range(*edited_range)

        imgui.separator()

        self.checkbox("simulate_wind", "Simulate Particles")

        self.combo("vector_data_type", "Data Type##vector", vm.vector_data_types)
        vector_heights = getattr(vm.vector_data_type, "heights", None)
        if vector_heights:
            self.combo(
                "vector_height_type", "Data Height##vector", vector_heights,
            )

        self.slider_float(
            "particle_speed", "Particle speed", 0.1, 3.0, format="%.1f",
        )
        self.slider_int(
            "num_particles", "Particle count", 10_000, 1_000_000,
            round_digits=4,
        )
        self.slider_power_2(
            "particle_resolution", "Particle Resolution", 7, 10,
        )
