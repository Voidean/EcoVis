from typing import override

from ui.components.base_component import ViewModelComponent
from ui.components.plot_content_component import PlotContentComponent
from ui.viewmodels.plot_view_model import (
    PlotViewModel,
    UserScriptGraphViewModel,
)


class PlotComponent(ViewModelComponent[PlotViewModel]):
    """Dockable composable facade for plot state."""

    def __init__(self, view_model: PlotViewModel):
        ViewModelComponent.__init__(self, view_model)
        self._plot_content = PlotContentComponent(view_model)
        self._plot_content_destroyed = False

    @override
    def render(self):
        self.prepare_render()
        self.render_plot()

    def render_plot(self):
        self._plot_content.render()

    @override
    def destroy(self):
        if not self._plot_content_destroyed:
            self._plot_content.destroy()
            self._plot_content_destroyed = True
        ViewModelComponent.destroy(self)


class UserScriptGraphComponent(PlotComponent):
    def __init__(self, title: str, plots):
        super().__init__(UserScriptGraphViewModel(title, plots))

    @property
    def display_name(self) -> str:
        return self.view_model.title
