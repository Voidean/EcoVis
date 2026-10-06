"""Component selection for graph representations."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ui.components.base_component import Component
from ui.components.graph_display.calendar import (
    CalendarHeatmapContentComponent,
)
from ui.components.graph_display.plot import (
    AreaContentComponent,
    CumulativeYieldContentComponent,
    DistributionContentComponent,
    GraphDisplayComponent,
    HistogramContentComponent,
    ScatterContentComponent,
    TimeSeriesContentComponent,
)
from ui.components.image_component import WindroseImageComponent
from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from ui.viewmodels.graph_display.calendar import CalendarHeatmapViewModel
from ui.viewmodels.graph_display.frequency import HistogramViewModel, ScatterViewModel
from ui.viewmodels.graph_display.time_series import MeanSquaredErrorViewModel, AreaViewModel, CumulativeYieldViewModel, \
    TimeSeriesViewModel
from ui.viewmodels.windrose_view_model import WindroseViewModel

if TYPE_CHECKING:
    from ui.viewmodels.graph_view_model import GraphViewModel


class GraphDisplaySwitcherComponent(Component):
    """Keep all representation components alive and render the selected one."""

    def __init__(self, view_model: GraphViewModel):
        super().__init__(view_model)
        self.view_model = view_model
        self._components = {
            display.display_name: create_graph_display_component(display)
            for display in view_model.display_view_models
        }

    @override
    def render(self):
        self._components[self.view_model.plot_view].render()

    def destroy(self):
        for component in self._components.values():
            component.destroy()
        self._components.clear()
        Component.destroy(self)


def create_graph_display_component(
        view_model: GraphDisplayViewModel,
) -> GraphDisplayComponent | CalendarHeatmapContentComponent | WindroseImageComponent:
    """Map display state to rendering without coupling ViewModels to ImGui."""
    if isinstance(view_model, CalendarHeatmapViewModel):
        return CalendarHeatmapContentComponent(view_model)
    if isinstance(view_model, WindroseViewModel):
        return WindroseImageComponent(view_model)
    if isinstance(view_model, HistogramViewModel):
        return HistogramContentComponent(view_model)
    if isinstance(view_model, ScatterViewModel):
        return ScatterContentComponent(view_model)
    if isinstance(view_model, MeanSquaredErrorViewModel):
        return TimeSeriesContentComponent(view_model)
    if isinstance(view_model, AreaViewModel):
        return AreaContentComponent(view_model)
    if isinstance(view_model, CumulativeYieldViewModel):
        return CumulativeYieldContentComponent(view_model)
    if isinstance(view_model, TimeSeriesViewModel):
        return TimeSeriesContentComponent(view_model)
    return DistributionContentComponent(view_model)
