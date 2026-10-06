from collections.abc import Callable

from imgui_bundle import imgui

from input import Input
from model.state.view_state import view_state
from rendering.scene.camera import Camera
from service.camera_flight import CameraFlight
from ui.components.map_weather_control_component import MapWeatherControlComponent
from ui.docking.workspace import default_docking_workspace
from ui.components.data_component_options import DATA_COMPONENT_OPTIONS
from ui.components.data_graph_components import WeatherGraphComponent
from ui.components.measurement_points import MeasurementPoints
from ui.views.view_types import ViewId, ViewMetadata
from ui.views.compass_view import CompassView
from ui.components.config_component import ConfigComponent
from ui.views.content_view import ContentView
from ui.views.data_view_group import DataViewGroup
from ui.persistence.data_view_persistence import capture_data_views, restore_data_views
from ui.views.debug_view import DebugView
from ui.views.fps_view import FpsView
from ui.views.main_menu_view import MainMenuView
from ui.views.time_control_view import TimeControlView
from ui.views.view_registry import ViewRegistry
from ui.viewmodels.main_menu_view_model import MainMenuViewModel
from util.config import config


class UIManager:
    def __init__(
            self,
            input: Input,
            camera: Camera,
            window_chrome,
            camera_flight: CameraFlight,
            graphics_preview_handler: Callable,
            measurement_data_textures,
    ):
        self.input = input
        self.docking_workspace = default_docking_workspace
        self.view_registry = ViewRegistry(view_state)
        self.config_component = ConfigComponent(
            input,
            graphics_preview_handler,
        )
        self.view_registry.register(ViewId.TIME_CONTROL, TimeControlView())
        self.view_registry.register(ViewId.DEBUG, DebugView())
        self.view_registry.register(
            ViewId.CONFIG,
            ContentView(
                ViewMetadata(ViewId.CONFIG, "Configuration"),
                self.config_component,
                destroy_on_close=False,
            ),
        )
        self.main_menu_view = MainMenuView(
            window_chrome,
            MainMenuViewModel(self.view_registry),
            camera_flight,
        )

        self.data_views = DataViewGroup(
            ViewMetadata(ViewId.DATA, "Data Analysis"),
            WeatherGraphComponent,
            component_options=DATA_COMPONENT_OPTIONS,
        )
        self.view_registry.register(ViewId.DATA, self.data_views)
        if config.data_windows.save_contents:
            restore_data_views(
                self.data_views,
                config.data_windows.snapshot,
            )

        map_weather_control_view = ContentView(
            ViewMetadata(ViewId.MAP_WEATHER_CONTROL, "Map Weather Control"),
            MapWeatherControlComponent(),
        )
        self.view_registry.register(
            ViewId.MAP_WEATHER_CONTROL,
            map_weather_control_view,
        )

        self.measurement_points = MeasurementPoints(
            camera,
            measurement_data_textures,
        )
        self.compass_view = CompassView()
        self.fps_view = FpsView()

    def render(self, dt, camera: Camera):
        imgui.new_frame()
        self.docking_workspace.start_frame()

        self.main_menu_view.render(dt, camera)

        for _, view in self.view_registry.enabled_items():
            view.render(dt)

        if not view_state.enabled_views.get(ViewId.CONFIG, False):
            self.config_component.hide()

        self.measurement_points.render(self.input.mouse_pos)
        self.compass_view.render(camera)
        if config.window.show_fps:
            self.fps_view.render(dt)

        self.docking_workspace.finish_frame(
            mouse_released=imgui.is_mouse_released(0),
            drag_payload_active=(
                imgui.get_drag_drop_payload_py_id() is not None
            ),
        )

        imgui.render()
        self.input.keys_pressed.clear()

    def destroy(self):
        enabled_views = dict(view_state.enabled_views)
        snapshot = (
            capture_data_views(self.data_views)
            if config.data_windows.save_contents
            else {"version": 1, "windows": []}
        )
        config.save({"data_windows": {"snapshot": snapshot}})
        for view in self.view_registry.values():
            view.destroy()
        self.view_registry.clear()
        # Closing renderer objects during shutdown must not change which
        # views are restored on the next application start.
        view_state.enabled_views.clear()
        view_state.enabled_views.update(enabled_views)
        self.measurement_points.destroy()
        self.compass_view.destroy()
        self.fps_view.destroy()
        self.main_menu_view.destroy()
