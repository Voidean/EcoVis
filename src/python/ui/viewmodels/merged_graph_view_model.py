from collections.abc import Sequence
from dataclasses import dataclass

from ui.view_model import ViewModel
from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from ui.viewmodels.graph_view_model import GraphViewModel
from ui.viewmodels.plot_view_model import Plots


@dataclass(frozen=True)
class MergedPlotSnapshot:
    plots: Plots
    titles: dict[str, str]
    units: dict[str, str]
    highlighted: str | None
    signature: tuple
    loading: bool
    uses_time_axis: bool
    incompatible_x_axes: bool
    x_axis_label: str
    render_kinds: dict[str, str]
    bar_widths: dict[str, float | None]
    unsupported_views: tuple[str, ...]


class MergedGraphViewModel(ViewModel):
    """Coordinates child graph ViewModels for a merged plot component."""

    def __init__(self, graphs: Sequence[GraphViewModel]):
        super().__init__()
        self._graphs = list(graphs)
        self.plot_views = self._common_plot_views()
        if not self.plot_views:
            raise ValueError("Merged graphs have no compatible plot view")
        self._display_view_models = self._create_display_view_models()
        self.plot_view = self._initial_plot_view()

    @property
    def graphs(self) -> tuple[GraphViewModel, ...]:
        return tuple(self._graphs)

    @property
    def active_display_view_model(self) -> GraphDisplayViewModel:
        return self._display_view_models[self.plot_view]

    @property
    def label(self) -> str:
        return "Merged Graph"

    @property
    def label_x(self) -> str:
        return ""

    @property
    def label_y(self) -> str:
        return "Value"

    @property
    def highlighted(self):
        return None

    @property
    def loading(self) -> bool:
        return any(graph.loading for graph in self.graphs)

    @property
    def raw_data_revision(self) -> tuple:
        return tuple(
            (
                id(graph),
                graph.raw_data_revision,
                graph.label_y,
            )
            for graph in self.graphs
        )

    def set_plot_view(self, plot_view: str):
        """Select one shared representation for every graph in the merge."""
        if plot_view not in self.plot_views:
            return
        if (
                plot_view == self.plot_view
                and all(graph.plot_view == plot_view for graph in self.graphs)
        ):
            return
        self.plot_view = plot_view

    def _common_plot_views(self) -> tuple[str, ...]:
        if not self._graphs:
            return ()
        available_in_every_graph = set(self._graphs[0].mergeable_plot_views)
        for graph in self._graphs[1:]:
            available_in_every_graph.intersection_update(
                graph.mergeable_plot_views,
            )
        return tuple(
            view
            for view in self._graphs[0].mergeable_plot_views
            if view in available_in_every_graph
        )

    def _initial_plot_view(self) -> str:
        current_views = {graph.plot_view for graph in self.graphs}
        if len(current_views) == 1 and self._graphs[0].plot_view in self.plot_views:
            return self._graphs[0].plot_view
        if "Time series" in self.plot_views:
            return "Time series"
        return self.plot_views[0]

    def _create_display_view_models(
            self,
    ) -> dict[str, GraphDisplayViewModel]:
        first_graph_views = {
            view.display_name: view
            for view in self._graphs[0].display_view_models
        }
        return {
            plot_view: type(first_graph_views[plot_view])(self)
            for plot_view in self.plot_views
        }

    def tick(self):
        if self.destroyed:
            return
        for graph in self.graphs:
            graph.tick()
        self.active_display_view_model.tick()

    def displayed_plots(self) -> Plots:
        return self._raw_data()[0]

    def raw_plot_title(self, plot_id: str) -> str:
        return self._raw_data()[1].get(str(plot_id), str(plot_id))

    def distribution_maximum(self, _, values) -> float:
        return float(values.max())

    def snapshot(self) -> MergedPlotSnapshot:
        _, _, raw_units = self._raw_data()
        display = self.active_display_view_model
        plots = display.visible_plots()
        titles = {
            key: display.visible_plot_title(key)
            for key in plots
        }
        units = (
            {
                key: raw_units.get(key, display.plot_y_label or "Value")
                for key in plots
            }
            if display.preserves_source_units
            else {
                key: display.plot_y_label or "Value"
                for key in plots
            }
        )
        signature = (
            display.revision,
            tuple(
                (key, id(x_data), id(y_data), count)
                for key, (x_data, y_data, count) in plots.items()
            ),
        )

        return MergedPlotSnapshot(
            plots=plots,
            titles=titles,
            units=units,
            highlighted=None,
            signature=signature,
            loading=self.loading,
            uses_time_axis=display.uses_time_axis,
            incompatible_x_axes=False,
            x_axis_label=display.label_x,
            render_kinds={key: display.render_kind for key in plots},
            bar_widths={key: display.bar_width for key in plots},
            unsupported_views=(),
        )

    def _raw_data(self) -> tuple[Plots, dict[str, str], dict[str, str]]:
        plots = {}
        titles = {}
        units = {}
        for graph_index, graph in enumerate(self.graphs):
            for plot_key, plot_data in graph.displayed_plots().items():
                merged_key = f"{graph_index}:{plot_key}"
                plots[merged_key] = plot_data
                titles[merged_key] = (
                    f"{graph.display_name} {graph_index + 1}: "
                    f"{graph.raw_plot_title(plot_key)}"
                )
                units[merged_key] = graph.label_y or "Value"
        return plots, titles, units

    def destroy(self):
        if self.destroyed:
            return
        # Child components own their respective ViewModels. The coordinator
        # only holds non-owning references to them.
        for view_model in self._display_view_models.values():
            view_model.destroy()
        self._display_view_models.clear()
        self._graphs.clear()
        super().destroy()
