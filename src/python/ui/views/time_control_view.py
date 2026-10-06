from imgui_bundle import imgui

from ui.viewmodels.time_control_view_model import TimeControlViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class TimeControlView(View[TimeControlViewModel]):
    def __init__(self, view_model: TimeControlViewModel | None = None):
        super().__init__(
            ViewMetadata(ViewId.TIME_CONTROL, "Time Control"),
            view_model or TimeControlViewModel(),
        )

    def render(self, dt):
        self.prepare_render()
        vm = self.view_model
        imgui.begin("Time Control")

        # Play / Pause
        if vm.paused:
            if imgui.button("Play"):
                vm.toggle_paused()
        else:
            if imgui.button("Pause"):
                vm.toggle_paused()

        # Speed slider
        changed, speed = imgui.slider_float(
            "Speed",
            vm.speed,
            0.0,
            24.0,
            format="%.2f hours/sec"
        )
        if changed:
            vm.set_speed(speed)

        imgui.separator()

        self.datepicker(
            "input_dt",
            vm,
            ["Year", "Month", "Day", "Hour", "Minute"],
            same_line=False,
        )

        if imgui.button("Set Time"):
            vm.apply_input_time()

        if imgui.button("Sync From Current"):
            vm.sync_input_from_current()

        imgui.separator()

        imgui.spacing()
        imgui.text(f"UTC:   {vm.utc_time_text}")
        imgui.spacing()
        imgui.text(f"Local: {vm.local_time_text}")
        imgui.spacing()

        imgui.end()
