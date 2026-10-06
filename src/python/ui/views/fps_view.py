from imgui_bundle import imgui

from ui.viewmodels.fps_view_model import FpsViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class FpsView(View[FpsViewModel]):
    def __init__(self, view_model: FpsViewModel | None = None):
        super().__init__(
            ViewMetadata(ViewId.FPS, "FPS"),
            view_model or FpsViewModel(),
        )

    def render(self, dt):
        self.view_model.set_delta_time(dt)
        self.prepare_render()
        imgui.set_next_window_pos((5.0, 25.0))
        imgui.set_next_window_size((120.0, 35.0))

        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_inputs
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_background
        )
        imgui.begin("##fps_overlay", flags=flags)
        imgui.text(f"FPS: {self.view_model.fps:.1f}")
        imgui.end()
