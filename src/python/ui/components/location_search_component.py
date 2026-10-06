from imgui_bundle import imgui

from rendering.scene.camera import Camera
from service.camera_flight import CameraFlight
from ui.components.base_component import ViewModelComponent
from ui.viewmodels.location_search_view_model import LocationSearchViewModel

POPUP_ID = "##location_search_results"
class LocationSearchComponent(ViewModelComponent[LocationSearchViewModel]):
    def __init__(
            self,
            camera_flight: CameraFlight | None = None,
            view_model: LocationSearchViewModel | None = None,
    ):
        super().__init__(
            view_model
            or LocationSearchViewModel(camera_flight=camera_flight)
        )

    def render(self, camera: Camera):
        vm = self.view_model
        self.prepare_render()

        available_width = imgui.get_content_region_avail().x
        search_width = min(420.0, max(220.0, available_width * 0.32))
        imgui.set_next_item_width(search_width)
        changed, query = imgui.input_text_with_hint(
            "##location_search", "Search locations...", vm.query
        )
        input_min = imgui.get_item_rect_min()
        input_max = imgui.get_item_rect_max()

        should_open = False
        if changed:
            vm.search(query, camera)
            should_open = bool(vm.query)
        elif imgui.is_item_activated() and vm.query:
            should_open = True

        if should_open and not imgui.is_popup_open(POPUP_ID):
            imgui.open_popup(POPUP_ID)

        imgui.set_next_window_pos((input_min.x, input_max.y))
        imgui.set_next_window_size_constraints((search_width, 0.0), (search_width, 360.0))
        popup_flags = (
            imgui.WindowFlags_.no_focus_on_appearing
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_saved_settings
        )
        if imgui.begin_popup(POPUP_ID, popup_flags):
            self._render_popup()
            imgui.end_popup()

        return input_max

    def _render_popup(self):
        vm = self.view_model
        if not vm.can_search:
            imgui.text_disabled("Enter at least 2 characters")
            return

        if vm.loading:
            imgui.text_disabled("Searching...")
        elif vm.error:
            imgui.text_wrapped(vm.error)
        elif not vm.locations:
            imgui.text_disabled("No matching locations")

        if not vm.locations:
            return

        if imgui.is_key_pressed(imgui.Key.down_arrow):
            vm.move_selection(1)
        if imgui.is_key_pressed(imgui.Key.up_arrow):
            vm.move_selection(-1)

        selected = None
        if imgui.is_key_pressed(imgui.Key.enter, repeat=False):
            selected = vm.selected_location

        for index, location in enumerate(vm.locations):
            population = vm.format_population(location.population)
            details = [value for value in (location.admin1, location.country) if value]
            if population:
                details.append(population)
            suffix = f" - {', '.join(details)}" if details else ""
            label = f"{location.name}{suffix}##location_{location.latitude}_{location.longitude}"
            clicked, _ = imgui.selectable(label, index == vm.selected_index)
            if clicked:
                selected = location

        if selected is not None:
            vm.select_location(selected)
            imgui.close_current_popup()
