from imgui_bundle import imgui

from ui.viewmodels.debug_view_model import DebugViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class DebugView(View[DebugViewModel]):
    def __init__(self, view_model: DebugViewModel | None = None):
        super().__init__(
            ViewMetadata(ViewId.DEBUG, "Debug"),
            view_model or DebugViewModel(),
        )

    def render(self, dt):
        self.view_model.set_delta_time(dt)
        self.prepare_render()
        vm = self.view_model

        imgui.begin("Debug")
        imgui.text(f"FPS: {vm.fps:.1f}")

        self.checkbox_value(
            "Display Tile Boundaries", vm._state.display_tile_boundaries,
            lambda value: vm.set_value("display_tile_boundaries", value),
        )

        if vm.tile_counts:
            imgui.separator()
            imgui.text(f"Total num of LoD tiles: {vm.total_tiles}")
            for level, num in vm.tile_counts:
                imgui.text(f"Level {level}: {num}")

        imgui.end()
