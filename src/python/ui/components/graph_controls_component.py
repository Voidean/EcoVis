from typing import override

from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.components.sync_component import SyncControlsComponent
from ui.viewmodels.graph_view_model import GraphViewModel
from ui.viewmodels.power_graph_view_model import PowerPlantGraphViewModel
from ui.viewmodels.weather_graph_view_model import WeatherGraphViewModel


class GraphConfigurationComponent(Component):
    """Controls shared by all loaded graph types."""

    def __init__(self, view_model: GraphViewModel):
        super().__init__(view_model)
        self.view_model = view_model

    @override
    def render(self, *, show_view_selector: bool = True):
        view_model = self.view_model
        if show_view_selector:
            self._combo_control(
                "View",
                getattr(
                    view_model,
                    "selectable_plot_views",
                    view_model.plot_views,
                ),
                view_model.plot_view,
                view_model.set_plot_view,
            )

        if getattr(view_model, "plot_view", None) != "Windrose":
            imgui.text("Number of prior years:")
            imgui.same_line()
            imgui.set_next_item_width(80)
            changed, new_value = imgui.input_int(
                f"##years_prior_{self.instance_id}",
                view_model.years_prior,
            )
            if changed:
                view_model.set_years_prior(new_value)


class PowerPlantGraphControlsComponent(Component):
    """Rendering-only controls for power-plant graph state."""

    def __init__(self, view_model: PowerPlantGraphViewModel):
        super().__init__(view_model)
        self.view_model = view_model
        self.sync_controls = SyncControlsComponent(view_model)

    @override
    def render(self):
        view_model = self.view_model
        self.sync_controls.render()

        if view_model.host:
            self._combo_control(
                f"##sync_mode_{self.instance_id}",
                view_model.sync_options,
                view_model.sync_mode,
                view_model.set_sync_mode,
            )

        imgui.separator()

        if view_model.plant_info:
            plant = view_model.plant_info
            imgui.text("Power Plant Info:")
            self._combo_control(
                f"##plant_info_selection_{self.instance_id}",
                view_model.plants,
                plant,
                view_model.select_plant,
                iter_buttons=True,
            )
            imgui.text(f"Name: {plant.shortname}")
            imgui.text(
                f"Location: N {plant.latitude:.2f}°, "
                f"E {plant.longitude:.2f}°, "
                f"H {plant.elevation:.0f}m asl"
            )
            imgui.text(f"Energy type: {plant.energietraeger}")
            imgui.text(f"Company: {plant.firmenname}")
            imgui.text(f"Max Power: {plant.leistung_kw} KW")

            if not view_model.host or "Location" not in view_model.sync_mode:
                if imgui.button(
                        f"Remove Plant from Overview##{self.instance_id}"
                ):
                    view_model.remove_selected_plant()

        imgui.separator()
        self._combo_control(
            f"##use_prognosis_{self.instance_id}",
            ["Measurements", "Prognosis", "Comparison"],
            view_model.mode,
            view_model.set_mode,
        )

    @override
    def destroy(self):
        self.sync_controls.destroy()
        Component.destroy(self)


class WeatherGraphControlsComponent(Component):
    """Rendering-only controls for weather graph state."""

    def __init__(self, view_model: WeatherGraphViewModel):
        super().__init__(view_model)
        self.view_model = view_model
        self.sync_controls = SyncControlsComponent(view_model)

    @override
    def render(self):
        view_model = self.view_model
        self.sync_controls.render()

        if view_model.host:
            self._combo_control(
                f"##sync_mode_{self.instance_id}",
                ["Time", "Location", "Time and Location"],
                view_model.sync_mode,
                view_model.set_sync_mode,
            )

        imgui.separator()

        if view_model.model_info:
            imgui.text(f"Data Source: {view_model.model_info}")

        if view_model.resolved_geo_pos:
            position = view_model.resolved_geo_pos
            imgui.text(
                f"Location: N {position.lat_deg:.4f}°, "
                f"E {position.lon_deg:.4f}°"
            )

        if view_model.plot_view == "Windrose":
            return

        self._combo_control(
            "Frequency",
            view_model.data_frequencies,
            view_model.data_frequency,
            view_model.set_data_frequency,
        )
        self._combo_control(
            "Datatype",
            list(view_model.data_frequency),
            view_model.data_type,
            view_model.set_data_type,
        )

        if view_model.requires_orientation:
            changed, tilt = imgui.slider_int(
                f"Tilt##tilt_{self.instance_id}",
                view_model.tilt,
                0,
                90,
                format="%d°",
            )
            if changed:
                view_model.set_tilt(tilt, reload=False)
            if imgui.is_item_deactivated_after_edit():
                view_model.request_reload()
            if isinstance(view_model.azimuth, tuple):
                imgui.text(
                    "Azimuth: "
                    + " / ".join(
                        f"{value}°" for value in view_model.azimuth
                    )
                )
            else:
                changed, azimuth = imgui.slider_int(
                    (
                        "Azimuth(-90° E, 0° S, 90° W, +/-180° N)"
                        f"##azimuth_{self.instance_id}"
                    ),
                    view_model.azimuth,
                    -180,
                    180,
                    format="%d°",
                )
                if changed:
                    view_model.set_azimuth(azimuth, reload=False)
                if imgui.is_item_deactivated_after_edit():
                    view_model.request_reload()

    @override
    def destroy(self):
        self.sync_controls.destroy()
        Component.destroy(self)
