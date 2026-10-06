import re
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np

from scripts.user_script import PlotData
from ui.view_model import ViewModel
from ui.viewmodels.plot_source import (
    PlotSource,
    PlotSourceKey,
    discover_plot_sources,
)
from util.paths import EXTERNAL_DATA


ArchiveWriter = Callable[..., object]


class DataExportViewModel(ViewModel):
    """Select already loaded plot data and write it as NumPy arrays."""

    def __init__(
            self,
            component_provider: Callable[[], Iterable],
            *,
            archive_writer: ArchiveWriter = np.savez,
    ):
        super().__init__()
        self.enabled = False
        self.status_text = ""
        self.status_is_error = False
        self.destination = EXTERNAL_DATA / "data-view-export.npz"
        self._selected_sources: set[PlotSourceKey] = set()
        self._component_provider = component_provider
        self._archive_writer = archive_writer

    @property
    def selected_sources(self) -> frozenset[PlotSourceKey]:
        return frozenset(self._selected_sources)

    def toggle_enabled(self):
        self.enabled = not self.enabled

    def available_plot_sources(self) -> list[PlotSource]:
        return discover_plot_sources(
            self._component_provider,
            include_composite_children=True,
        )

    def is_selected(self, source_key: PlotSourceKey) -> bool:
        return source_key in self._selected_sources

    def set_source_selected(
            self,
            source_key: PlotSourceKey,
            selected: bool,
    ):
        if selected:
            self._selected_sources.add(source_key)
        else:
            self._selected_sources.discard(source_key)
        self.status_text = ""
        self.status_is_error = False

    def select_all(self, sources: Iterable[PlotSource] | None = None):
        sources = self.available_plot_sources() if sources is None else sources
        self._selected_sources.update(source.key for source in sources)
        self.status_text = ""
        self.status_is_error = False

    def clear_selection(self):
        self._selected_sources.clear()
        self.status_text = ""
        self.status_is_error = False

    def selected_plot_sources(
            self,
            sources: Iterable[PlotSource] | None = None,
    ) -> list[PlotSource]:
        """Resolve selections against the current DataView contents.

        Components and plots can disappear or move while this control exists.
        Resolving keys immediately before export prevents stale selections from
        exporting data that no longer belongs to this DataView.
        """
        sources = self.available_plot_sources() if sources is None else sources
        return [
            source
            for source in sources
            if source.key in self._selected_sources
        ]

    def export(self, destination: str | Path) -> Path | None:
        try:
            selected = self.selected_plot_sources()
            written_path = self.write_archive(destination, selected)
        except Exception as error:
            self.status_text = f"Export failed: {error}"
            self.status_is_error = True
            return None

        self.destination = written_path
        self.status_text = (
            f"Exported {len(selected)} time series to {written_path}"
        )
        self.status_is_error = False
        return written_path

    def write_archive(
            self,
            destination: str | Path,
            sources: Iterable[PlotSource],
    ) -> Path:
        sources = tuple(sources)
        if not sources:
            raise ValueError("Select at least one time series")

        destination = self._normalized_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        arrays = {
            self._archive_key(index, source.display_name): self.plot_data_array(
                source.data
            )
            for index, source in enumerate(sources)
        }
        self._archive_writer(destination, **arrays)
        return destination

    @staticmethod
    def plot_data_array(data: PlotData) -> np.ndarray:
        x_data, y_data, count = data
        x_data = np.asarray(x_data)
        y_data = np.asarray(y_data)
        if x_data.ndim != 1 or y_data.ndim != 1:
            raise ValueError("Time-series axes must be one-dimensional")

        sample_count = int(count)
        if sample_count != count or sample_count < 0:
            raise ValueError("Time-series sample count is invalid")
        if sample_count > len(x_data) or sample_count > len(y_data):
            raise ValueError("Time-series sample count exceeds its array size")

        try:
            return np.column_stack((
                x_data[:sample_count],
                y_data[:sample_count],
            )).astype(np.float64, copy=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Time-series values must be numeric") from error

    @staticmethod
    def _normalized_destination(destination: str | Path) -> Path:
        destination = Path(destination).expanduser()
        if not destination.name:
            raise ValueError("Choose an export destination")
        if destination.suffix.lower() == ".npz":
            destination = destination.with_suffix(".npz")
        else:
            destination = destination.with_name(destination.name + ".npz")
        return destination

    @staticmethod
    def _archive_key(index: int, display_name: str) -> str:
        name = re.sub(r"[^0-9A-Za-z]+", "_", display_name).strip("_")
        return f"series_{index:03d}_{name or 'time_series'}"
