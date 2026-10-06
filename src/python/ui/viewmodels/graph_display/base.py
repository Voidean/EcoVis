"""Common state and source contract for graph representations."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from ui.view_model import ViewModel
from ui.viewmodels.plot_view_model import (
    GraphBounds,
    Plots,
    PlotViewModel,
    default_graph_bounds,
)


class GraphDisplaySource(Protocol):
    label: str
    label_x: str
    label_y: str
    highlighted: str | None
    loading: bool

    @property
    def raw_data_revision(self) -> tuple: ...

    def displayed_plots(self) -> Plots: ...

    def raw_plot_title(self, plot_id: str) -> str: ...

    def distribution_maximum(
            self,
            plot_id: str,
            values: np.ndarray,
    ) -> float: ...


class GraphDisplayViewModel(ViewModel):
    """Base state shared by every selectable graph representation."""

    display_name = "Graph"
    render_kind = "line"
    uses_time_axis = True
    merge_supported = True
    preserves_source_units = False
    include_zero_baseline = False
    supports_ignore_zeros = False
    empty_message: str | None = None

    def __init__(self, source: GraphDisplaySource):
        super().__init__()
        self.source = source
        self.graph_bounds: GraphBounds = default_graph_bounds()
        self.bounds_revision = 0
        self._settings_revision = 0
        self.ignore_zero_values = False
        self._plots_cache: Plots | None = None
        self._plots_cache_key: tuple | None = None
        self._zero_share_cache = 0.0
        self._zero_share_cache_key: tuple | None = None

    @property
    def revision(self) -> tuple:
        return (
            type(self).__name__,
            self.source.raw_data_revision,
            self._settings_revision,
        )

    @property
    def label(self) -> str:
        return self.source.label

    @property
    def label_x(self) -> str:
        return self.source.label_x if self.uses_time_axis else self.source.label_y

    @property
    def label_y(self) -> str:
        return self.source.label_y

    @property
    def highlighted(self):
        return self.source.highlighted

    @property
    def loading(self) -> bool:
        return self.source.loading

    @property
    def x_axis_key(self) -> tuple[str, str]:
        return (
            ("time", "")
            if self.uses_time_axis
            else ("linear", self.label_x)
        )

    @property
    def plot_y_label(self) -> str:
        return self.label_y

    @property
    def bar_width(self) -> float | None:
        return None

    def visible_plots(self) -> Plots:
        cache_key = self.revision
        if self._plots_cache_key != cache_key:
            self._plots_cache = self._transform(self.source.displayed_plots())
            self._plots_cache_key = cache_key
        return self._plots_cache or {}

    def visible_plot_title(self, plot_id: str) -> str:
        return self.source.raw_plot_title(plot_id)

    @property
    def zero_share(self) -> float:
        cache_key = self.source.raw_data_revision
        if self._zero_share_cache_key == cache_key:
            return self._zero_share_cache
        finite_count = 0
        zero_count = 0
        for _, values, count in self.source.displayed_plots().values():
            finite = np.asarray(values[:count], dtype=np.float64)
            finite = finite[np.isfinite(finite)]
            finite_count += len(finite)
            zero_count += int(np.count_nonzero(finite == 0))
        self._zero_share_cache = (
            zero_count / finite_count if finite_count else 0.0
        )
        self._zero_share_cache_key = cache_key
        return self._zero_share_cache

    def set_ignore_zero_values(self, ignore: bool):
        if not self.supports_ignore_zeros or ignore == self.ignore_zero_values:
            return
        self.ignore_zero_values = ignore
        self._settings_changed()

    def update_plot_bounds(self):
        self.graph_bounds = PlotViewModel.calculate_plot_bounds(
            self.visible_plots(),
        )
        if self.include_zero_baseline and self.visible_plots():
            self.graph_bounds["y_min"] = min(0.0, self.graph_bounds["y_min"])
            self.graph_bounds["y_max"] = max(0.0, self.graph_bounds["y_max"])
        self.bounds_revision += 1

    def invalidate(self):
        self._plots_cache = None
        self._plots_cache_key = None
        self._zero_share_cache_key = None

    def _settings_changed(self):
        self._settings_revision += 1
        self.invalidate()
        self.update_plot_bounds()

    def _transform(self, source_plots: Plots) -> Plots:
        return source_plots

    def _finite_values(self, raw_values, count: int) -> np.ndarray:
        values = np.asarray(raw_values[:count], dtype=np.float64)
        values = values[np.isfinite(values)]
        if self.ignore_zero_values:
            values = values[values != 0]
        return values

    def destroy(self):
        if self.destroyed:
            return
        self.invalidate()
        self.source = None
        super().destroy()
