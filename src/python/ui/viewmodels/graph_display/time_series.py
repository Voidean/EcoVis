"""Time-axis graph representations."""

import numpy as np

from ui.viewmodels.graph_display.base import (
    GraphDisplaySource,
    GraphDisplayViewModel,
)
from ui.viewmodels.plot_view_model import Plots


class TimeSeriesViewModel(GraphDisplayViewModel):
    display_name = "Time series"
    preserves_source_units = True


class AreaViewModel(GraphDisplayViewModel):
    """Shade differences between timestamp-aligned source series."""

    display_name = "Area"
    render_kind = "area"
    include_zero_baseline = True
    empty_message = "Area differences require at least two data series."

    def __init__(self, source: GraphDisplaySource):
        super().__init__(source)
        self._titles: dict[str, str] = {}

    @property
    def label_y(self) -> str:
        return f"Difference: {self.source.label_y}"

    @property
    def plot_y_label(self) -> str:
        return self.source.label_y

    def visible_plot_title(self, plot_id: str) -> str:
        return self._titles.get(plot_id, str(plot_id))

    def _transform(self, source_plots: Plots) -> Plots:
        self._titles = {}
        if len(source_plots) < 2:
            return {}

        transformed = {}
        paired_keys = set()
        measurements = {}
        prognoses = {}
        for plot_id, plot_data in source_plots.items():
            key = str(plot_id)
            if key.startswith("measurements:"):
                measurements[key.removeprefix("measurements:")] = (
                    plot_id,
                    plot_data,
                )
            elif key.startswith("prognosis:"):
                prognoses[key.removeprefix("prognosis:")] = (
                    plot_id,
                    plot_data,
                )

        for suffix in measurements:
            if suffix not in prognoses:
                continue
            measurement_id, measurement = measurements[suffix]
            prognosis_id, prognosis = prognoses[suffix]
            result = _series_difference(measurement, prognosis)
            if result is None:
                continue
            result_id = f"difference:{suffix}"
            transformed[result_id] = result
            self._titles[result_id] = (
                f"{self.source.raw_plot_title(measurement_id)} minus prognosis"
            )
            paired_keys.update((measurement_id, prognosis_id))

        remaining = [
            (plot_id, plot_data)
            for plot_id, plot_data in source_plots.items()
            if plot_id not in paired_keys
        ]
        if len(remaining) >= 2:
            reference_id, reference = remaining[0]
            for comparison_id, comparison in remaining[1:]:
                result = _series_difference(reference, comparison)
                if result is None:
                    continue
                result_id = f"difference:{reference_id}:{comparison_id}"
                transformed[result_id] = result
                self._titles[result_id] = (
                    f"{self.source.raw_plot_title(reference_id)} minus "
                    f"{self.source.raw_plot_title(comparison_id)}"
                )
        return transformed


class MeanSquaredErrorViewModel(AreaViewModel):
    """Plot the running mean squared error of aligned source series."""

    display_name = "Mean squared error"
    render_kind = "line"
    empty_message = (
        "Mean squared error requires at least two data series."
    )

    @property
    def label_y(self) -> str:
        return f"Mean squared error: ({self.source.label_y})\N{SUPERSCRIPT TWO}"

    @property
    def plot_y_label(self) -> str:
        return f"({self.source.label_y})\N{SUPERSCRIPT TWO}"

    def _transform(self, source_plots: Plots) -> Plots:
        differences = super()._transform(source_plots)
        transformed = {}
        for plot_id, (x_data, difference, count) in differences.items():
            squared_error = np.square(
                np.asarray(difference[:count], dtype=np.float64),
            )
            mse = np.cumsum(squared_error) / np.arange(1, count + 1)
            transformed[plot_id] = (x_data, mse, count)
            self._titles[plot_id] = f"MSE: {self._titles[plot_id]}"
        return transformed


class CumulativeYieldViewModel(GraphDisplayViewModel):
    """Integrate power samples over their real sampling intervals."""

    display_name = "Cumulative yield"
    include_zero_baseline = True

    @property
    def label_y(self) -> str:
        return "Energy [kWh]"

    def _transform(self, source_plots: Plots) -> Plots:
        transformed = {}
        for plot_id, (x_data, y_data, count) in source_plots.items():
            sample_count = min(count, len(x_data), len(y_data))
            if sample_count == 0:
                continue
            x_values = np.asarray(x_data[:sample_count], dtype=np.float64)
            power = np.asarray(y_data[:sample_count], dtype=np.float64)
            cumulative = np.zeros(sample_count, dtype=np.float64)
            if sample_count > 1:
                hours = np.diff(x_values) / 3600.0
                increments = (power[:-1] + power[1:]) * 0.5 * hours
                valid = (
                    np.isfinite(increments)
                    & np.isfinite(hours)
                    & (hours >= 0)
                )
                cumulative[1:] = np.cumsum(
                    np.where(valid, increments, 0.0),
                )
            transformed[plot_id] = (x_values, cumulative, sample_count)
        return transformed


def _series_difference(first, second):
    first_x, first_y, first_count = first
    second_x, second_y, second_count = second
    common, first_indices, second_indices = np.intersect1d(
        np.asarray(first_x[:first_count], dtype=np.float64),
        np.asarray(second_x[:second_count], dtype=np.float64),
        assume_unique=False,
        return_indices=True,
    )
    if len(common) == 0:
        return None
    difference = (
        np.asarray(first_y[:first_count], dtype=np.float64)[first_indices]
        - np.asarray(second_y[:second_count], dtype=np.float64)[second_indices]
    )
    finite = np.isfinite(common) & np.isfinite(difference)
    common = common[finite]
    difference = difference[finite]
    return (common, difference, len(common)) if len(common) else None
