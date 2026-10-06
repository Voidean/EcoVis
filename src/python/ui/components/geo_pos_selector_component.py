from typing import Callable, override, Any

from imgui_bundle import imgui

from model.geo_pos import GeoPos
from ui.components.base_component import ViewModelComponent
from ui.viewmodels.geo_pos_selector_view_model import GeoPosSelectorViewModel


class GeoPosSelectorComponent(ViewModelComponent[GeoPosSelectorViewModel]):
    def __init__(
            self,
            on_event: Callable[[GeoPos], Any] = lambda _geo_pos: None,
            consume=False,
            view_model: GeoPosSelectorViewModel | None = None,
    ):
        super().__init__(
            view_model or GeoPosSelectorViewModel(on_event, consume)
        )

    def render(self):
        vm = self.view_model
        self.prepare_render()
        if vm.selecting:
            if imgui.button("Stop Selecting"):
                vm.stop_selecting()
        else:
            if imgui.button("Select Position"):
                vm.start_selecting()

    def cancel(self):
        """Stop an active selection while keeping the component reusable."""
        self.view_model.stop_selecting()

    @override
    def hide(self):
        self.cancel()
