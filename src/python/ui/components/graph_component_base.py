from typing import override

from ui.components.base_component import Component
from ui.components.generic_components import DateTimeComponent
from ui.components.graph_controls_component import (
    GraphConfigurationComponent,
)
from ui.components.graph_display.switcher import GraphDisplaySwitcherComponent
from ui.components.plot_component import PlotComponent
from ui.viewmodels.graph_view_model import GraphViewModel


class GraphComponent(PlotComponent, DateTimeComponent):
    """Composable graph assembled from controls and a plot renderer."""

    def __init__(
            self,
            view_model: GraphViewModel,
            controls: Component,
    ):
        PlotComponent.__init__(self, view_model)
        self._plot_content.destroy()
        self._plot_content = GraphDisplaySwitcherComponent(view_model)
        self._graph_configuration = GraphConfigurationComponent(view_model)
        self._graph_controls = controls
        self._graph_children_destroyed = False

    @override
    def render(self):
        self.prepare_render()
        self.render_configuration()
        self.render_plot()

    def prepare_render(self):
        self.view_model.tick()

    def render_configuration(self, *, show_view_selector: bool = True):
        self._graph_controls.render()
        self._graph_configuration.render(show_view_selector=show_view_selector)

    @override
    def destroy(self):
        if not self._graph_children_destroyed:
            self._graph_controls.destroy()
            self._graph_configuration.destroy()
            self._graph_children_destroyed = True
        PlotComponent.destroy(self)
