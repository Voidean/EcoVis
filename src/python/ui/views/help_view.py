from typing import override

from imgui_bundle import imgui

from ui.viewmodels.help_view_model import HelpViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class HelpView(View[HelpViewModel]):
    """Compact visual guide to the application's main controls."""

    def __init__(self, view_model: HelpViewModel | None = None):
        super().__init__(
            ViewMetadata(ViewId.HELP, "UI guide"),
            view_model or HelpViewModel(),
        )
        self.preferred_size = (680, 700)

    @property
    def opened(self) -> bool:
        return self.view_model.opened

    @opened.setter
    def opened(self, value: bool):
        self.view_model.set_opened(value)

    @override
    def render(self, dt=0.0):
        self.prepare_render()
        vm = self.view_model
        if not vm.opened:
            return

        imgui.set_next_window_size(self.preferred_size, imgui.Cond_.first_use_ever)
        expanded, opened = imgui.begin("UI guide", p_open=vm.opened)
        vm.set_opened(opened)
        if not expanded:
            imgui.end()
            return

        self._heading("Map navigation and measurements")
        self._instruction("Use", ("Search location...",), "in the menu bar to move the map to a place.")
        imgui.text_wrapped(
            "Clicking on the Map creates a temporary measurement point; "
            "right-click the point to remove it."
        )

        self._heading("Application time")
        imgui.text_wrapped(
            "Time Control sets the application-wide simulation time. It is separate from "
            "the time spans used to load graphs in Data views."
        )
        self._instruction("Press", ("Play",), "to let time run and", ("Pause",), "to stop it.")
        imgui.text_wrapped(
            "While time is running, the sun and moon move and weather data displayed on "
            "the map update to the current simulation time."
        )
        self._instruction("Use", ("Speed",), "to control how quickly time advances.")
        self._instruction("Enter a date and time, then press", ("Set Time",), "to jump to it.")

        self._heading("Weather heatmaps and wind animation")
        self._instruction("Open", ("Windows",), "and enable", ("Map Weather Control",), ".")
        self._instruction("Enable", ("Data Overlay",), "to draw weather data as a heatmap.")
        self._instruction("Choose", ("Data Type",), ("Data Height",), "and", ("Gradient",), ".")
        imgui.text_wrapped(
            "Gradient Clamping maps the selected value interval across the full colour "
            "gradient. Drag its left and right handles inward until the displayed values "
            "cover a realistic range for the selected weather type. This helps to adjust "
            "the gradient to different heights and weather types."
        )
        self._instruction("Adjust the Gradient Slider", ("|==== Gradient Clamping ====|",), "by dragging the handles.")
        self._instruction("Enable", ("Simulate Particles",), "to animate vector data such as wind.")
        self._instruction("Select the wind", ("Data Type",), "and", ("Data Height",), ".")
        imgui.text_wrapped(
            "Particle speed changes animation speed. Particle count changes the density of "
            "the flow lines, while Particle Resolution changes their simulation detail. "
            "Higher count and resolution settings require more graphics performance."
        )
        self._instruction("Tune", ("Particle speed",), ("Particle count",), "and", ("Particle Resolution",), ".")

        self._heading("Data Window basics")
        self._instruction("Open", ("Windows",), "and enable the Data window.")
        self._instruction("Use", ("Add component...",), "to add a graph or wind rose.")
        self._instruction("Drag", ("Component                         [...]",), "to rearrange a panel.")
        imgui.text_wrapped(
            "The [...] menu moves a panel to another row or window, creates a new window, "
            "or removes the panel. Empty Data views remain open for new content."
        )

        self._heading("Selecting data for a panel")
        self._instruction("Press", ("Select Position",), "inside the panel, then click the map.")
        imgui.text_wrapped(
            "This position belongs to that Data panel and is independent of the location "
            "search in the menu bar."
        )
        self._instruction("Press", ("Stop Selecting",), "to cancel position selection.")
        self._instruction("You can edit the Time span for the data in the fields. Once you are done, press", ("Apply Time Changes",), ".")
        imgui.text_wrapped(
            "Graph-specific controls choose the weather variable, power plant, forecast "
            "mode, and other settings used to load the panel's data."
        )

        self._heading("Coordinating multiple panels")
        imgui.text_wrapped(
            "Direct synchronization creates a host/target relationship between two graphs. "
            "Later changes in the host are forwarded to the target.\n"
            "Starting a Synchronization:"
        )
        self._instruction("On the source graph, press", ("Sync another component to this",), ".")
        self._instruction("On the target graph, press", ("Sync to other component",), ".")
        self._instruction("Choose", ("Time",), ("Location",), "or", ("Time and Location",), "as the synchronization modes.")
        self._instruction("Use", ("Stop Syncing from Host",), "to make the target independent again.")
        imgui.text_wrapped(
            "Alternatively, when one Data window contains multiple compatible panels, "
            "window-wide controls appear at the top. These update all panels together "
            "without creating a host/target relationship."
        )
        self._instruction("Enable", ("One position selector for all",), "for one map position.")
        self._instruction("Enable", ("One date picker for all",), "for one shared time span.")

        self._heading("Graph views and comparisons")
        self._instruction(
            "Use",
            ("View: Time series",),
            "to select a time series, comparison such as mean squared error, "
            "or distribution like Weibull or Beta.",
        )
        imgui.text_wrapped(
            "Changing the view uses the already loaded data.\nTo compare multiple graphs in "
            "one plotting area, first place at least two graph panels in the same window."
        )
        self._instruction("With two or more graph panels, press", ("Merge graphs...",), ".")
        self._instruction("Select the desired graphs, then press", ("Merge selected",), ".")
        self._instruction("Use", ("Separate Merged Graph",), "to restore individual panels.")

        self._heading("Display and application settings")
        self._instruction("Open", ("Settings",), ("Map",), "for projection and map overlays.")
        self._instruction("Use", ("Power plants",), "to choose visible energy sources.")
        self._instruction("Open", ("Settings",), ("Config",), "for video settings and keybinds.")

        self._heading("Exporting time series")
        self._instruction(
            "In a Data view, press",
            ("Export Data as NumPy Arrays",),
            ".",
        )
        imgui.text_wrapped(
            "Select any number of its loaded time series. Exporting creates one "
            ".npz file for use in external Python scripts or notebooks."
        )
        imgui.text_wrapped(
            "Each series is a numeric (N, 2) array containing Unix timestamps in "
            "the first column and values in the second. EcoVis does not import "
            "these files."
        )
        imgui.end()

    @staticmethod
    def _heading(heading: str):
        imgui.separator_text(heading)

    @staticmethod
    def _instruction(*parts: str | tuple[str]):
        imgui.align_text_to_frame_padding()
        for index, part in enumerate(parts):
            if index:
                imgui.same_line()
            if isinstance(part, tuple):
                imgui.begin_disabled()
                imgui.small_button(f"{part[0]}##help_{id(parts)}_{index}")
                imgui.end_disabled()
            else:
                imgui.text(part)
