from collections.abc import Callable
from typing import TypeAlias

import numpy as np

from ui.view_model import ViewModel


PlotSeries: TypeAlias = tuple[np.ndarray, np.ndarray, int]
Plots: TypeAlias = dict[str, PlotSeries]
GraphBounds: TypeAlias = dict[str, float]


def default_graph_bounds() -> GraphBounds:
    return {"x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0}


class PlotViewModel(ViewModel):
    """Plot state and transformations shared by all plot components."""

    def __init__(self):
        ViewModel.__init__(self)
        self.plots: Plots = {}
        self.graph_bounds = default_graph_bounds()
        self.bounds_revision = 0
        self.label = ""
        self.label_x = ""
        self.label_y = ""
        self.highlighted = None
        self.loading = False
        self.error: Exception | None = None
        self.get_title: Callable[[str], str] = str
        self._plots_revision = 0

    @property
    def revision(self) -> tuple:
        return self._plots_revision,

    def tick(self):
        """Static plots have no per-frame application work."""

    def visible_plots(self) -> Plots:
        return self.plots

    def visible_plot_title(self, plot_id) -> str:
        return self.get_title(plot_id)

    def set_plots(self, plots: Plots):
        self.plots = plots
        self._plots_revision += 1
        self.update_plot_bounds()

    def update_plot_bounds(self):
        self.graph_bounds = self.calculate_plot_bounds(self.visible_plots())
        self.bounds_revision += 1

    @staticmethod
    def calculate_plot_bounds(plots: Plots) -> GraphBounds:
        bounds = {
            "x_min": float("inf"),
            "x_max": float("-inf"),
            "y_min": float("inf"),
            "y_max": float("-inf"),
        }
        has_data = False
        for x_data, y_data, count in plots.values():
            if count == 0:
                continue
            sample_count = min(count, len(x_data), len(y_data))
            x_values = np.asarray(x_data[:sample_count], dtype=np.float64)
            y_values = np.asarray(y_data[:sample_count], dtype=np.float64)
            finite = np.isfinite(x_values) & np.isfinite(y_values)
            if not np.any(finite):
                continue
            x_values = x_values[finite]
            y_values = y_values[finite]
            has_data = True
            bounds["x_min"] = min(float(x_values.min()), bounds["x_min"])
            bounds["x_max"] = max(float(x_values.max()), bounds["x_max"])
            bounds["y_min"] = min(float(y_values.min()), bounds["y_min"])
            bounds["y_max"] = max(float(y_values.max()), bounds["y_max"])
        if not has_data:
            return default_graph_bounds()

        x_span = bounds["x_max"] - bounds["x_min"]
        y_span = bounds["y_max"] - bounds["y_min"]
        # A timestamp's absolute magnitude is about 1e9, so deriving padding
        # from a lone X value would accidentally show months around one sample.
        x_padding = x_span * 0.02 if x_span else 0.5
        y_padding = y_span * 0.1 if y_span else max(
            abs(bounds["y_min"]) * 0.1,
            0.5,
        )
        bounds["x_min"] -= x_padding
        bounds["x_max"] += x_padding
        bounds["y_min"] -= y_padding
        bounds["y_max"] += y_padding
        return bounds

    def destroy(self):
        if self.destroyed:
            return
        self.plots.clear()
        ViewModel.destroy(self)


class UserScriptGraphViewModel(PlotViewModel):
    def __init__(self, title: str, plots: Plots):
        super().__init__()
        self.title = title
        self.label = title
        self.set_plots(plots)
