from typing import override

from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.viewmodels.plot_view_model import PlotViewModel
from util.plotting_util import plot, setup_time_plot


class PlotContentComponent(Component):
    """Composable ImPlot renderer for already prepared plot state."""

    def __init__(self, view_model: PlotViewModel):
        super().__init__(view_model)
        self.view_model = view_model
        self._applied_bounds_revision = -1

    @override
    def render(self):
        view_model = self.view_model
        plot(
            data=view_model.visible_plots(),
            label=f"{view_model.label}##plot_{self.instance_id}",
            label_x=view_model.label_x,
            label_y=view_model.label_y,
            apply_settings=self._apply_graph_settings,
            get_title=view_model.visible_plot_title,
            highlight_key=view_model.highlighted,
            loading=view_model.loading,
        )
        if imgui.button(f"Normalize Plot Bounds##plot_{self.instance_id}"):
            view_model.update_plot_bounds()

    def _apply_graph_settings(self):
        view_model = self.view_model
        setup_time_plot(
            view_model.graph_bounds,
            self._applied_bounds_revision != view_model.bounds_revision,
        )
        self._applied_bounds_revision = view_model.bounds_revision
