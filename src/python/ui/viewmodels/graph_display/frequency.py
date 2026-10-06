"""Binned absolute and relative frequency representations."""

import numpy as np

from ui.viewmodels.graph_display.base import (
    GraphDisplaySource,
    GraphDisplayViewModel,
)
from ui.viewmodels.plot_view_model import Plots


class ScatterViewModel(GraphDisplayViewModel):
    """Binned absolute frequency rendered as unconnected samples."""

    display_name = "Scatter"
    render_kind = "scatter"
    uses_time_axis = False
    supports_ignore_zeros = True

    def __init__(self, source: GraphDisplaySource, bin_count: int = 20):
        super().__init__(source)
        self.bin_count = min(max(int(bin_count), 5), 100)

    @property
    def label_y(self) -> str:
        return "Absolute frequency"

    @property
    def plot_y_label(self) -> str:
        return "Absolute frequency"

    def set_bin_count(self, bin_count: int):
        bin_count = min(max(int(bin_count), 5), 100)
        if bin_count == self.bin_count:
            return
        self.bin_count = bin_count
        self._settings_changed()

    def _transform(self, source_plots: Plots) -> Plots:
        finite_by_plot = _finite_plots(self, source_plots)
        if not finite_by_plot:
            return {}
        edges = _shared_histogram_edges(finite_by_plot, self.bin_count)
        centers = (edges[:-1] + edges[1:]) * 0.5
        transformed = {}
        for plot_id, values in finite_by_plot.items():
            counts, _ = np.histogram(values, bins=edges)
            transformed[plot_id] = (
                centers,
                counts.astype(np.float64),
                len(centers),
            )
        return transformed


class HistogramViewModel(GraphDisplayViewModel):
    """Compute comparable, grouped frequency bars for visible series."""

    display_name = "Histogram"
    render_kind = "bars"
    uses_time_axis = False
    supports_ignore_zeros = True

    def __init__(self, source: GraphDisplaySource, bin_count: int = 20):
        super().__init__(source)
        self.bin_count = min(max(int(bin_count), 5), 100)
        self._bar_width = 0.67
        self._bin_width = 1.0

    @property
    def label_y(self) -> str:
        return "Frequency [%]"

    @property
    def plot_y_label(self) -> str:
        return "Frequency [%]"

    @property
    def bar_width(self) -> float:
        return self._bar_width

    def set_bin_count(self, bin_count: int):
        bin_count = min(max(int(bin_count), 5), 100)
        if bin_count == self.bin_count:
            return
        self.bin_count = bin_count
        self._settings_changed()

    def _transform(self, source_plots: Plots) -> Plots:
        finite_by_plot = _finite_plots(self, source_plots)
        if not finite_by_plot:
            return {}
        edges = _shared_histogram_edges(finite_by_plot, self.bin_count)
        centers = (edges[:-1] + edges[1:]) * 0.5
        self._bin_width = float(edges[1] - edges[0])
        series_count = len(finite_by_plot)
        self._bar_width = self._bin_width * 0.85 / series_count
        transformed = {}
        for index, (plot_id, values) in enumerate(finite_by_plot.items()):
            counts, _ = np.histogram(values, bins=edges)
            percentages = counts.astype(np.float64) * (100.0 / len(values))
            offset = (index - (series_count - 1) / 2) * self._bar_width
            transformed[plot_id] = (
                centers + offset,
                percentages,
                len(centers),
            )
        return transformed

    def update_plot_bounds(self):
        super().update_plot_bounds()
        if self.visible_plots():
            self.graph_bounds["x_min"] -= self._bin_width * 0.5
            self.graph_bounds["x_max"] += self._bin_width * 0.5
            self.graph_bounds["y_min"] = 0.0


def _finite_plots(view_model, source_plots):
    return {
        plot_id: values
        for plot_id, (_, raw_values, count) in source_plots.items()
        if len(values := view_model._finite_values(raw_values, count))
    }


def _shared_histogram_edges(
        finite_by_plot: dict[str, np.ndarray],
        bin_count: int,
) -> np.ndarray:
    value_min = min(float(values.min()) for values in finite_by_plot.values())
    value_max = max(float(values.max()) for values in finite_by_plot.values())
    if value_min == value_max:
        padding = max(abs(value_min) * 0.05, 0.5)
        value_min -= padding
        value_max += padding
    return np.linspace(value_min, value_max, bin_count + 1)
