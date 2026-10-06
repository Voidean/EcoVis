"""Calendar heatmap aggregation and layout."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np

from ui.viewmodels.graph_display.base import (
    GraphDisplaySource,
    GraphDisplayViewModel,
)
from ui.viewmodels.plot_view_model import Plots


@dataclass(frozen=True)
class CalendarHeatmapSeries:
    plot_id: str
    title: str
    year: int
    values: np.ndarray
    start_date: date
    month_ticks: tuple[float, ...]
    month_labels: tuple[str, ...]


class CalendarHeatmapViewModel(GraphDisplayViewModel):
    """Aggregate samples by day and arrange them as week/day matrices."""

    display_name = "Calendar heatmap"
    render_kind = "calendar"
    uses_time_axis = False
    merge_supported = False

    def __init__(self, source: GraphDisplaySource):
        super().__init__(source)
        self._calendar_cache: tuple[CalendarHeatmapSeries, ...] = ()
        self._calendar_cache_key: tuple | None = None
        self.scale_min = 0.0
        self.scale_max = 1.0

    @property
    def label_x(self) -> str:
        return "Calendar week"

    @property
    def x_axis_key(self) -> tuple[str, str]:
        return "calendar", self.source.label_y

    def visible_plots(self) -> Plots:
        return {}

    def heatmaps(self) -> tuple[CalendarHeatmapSeries, ...]:
        cache_key = self.revision
        if self._calendar_cache_key != cache_key:
            self._calendar_cache = self._build_heatmaps(
                self.source.displayed_plots(),
            )
            self._calendar_cache_key = cache_key
            self._update_scale()
        return self._calendar_cache

    def invalidate(self):
        super().invalidate()
        self._calendar_cache = ()
        self._calendar_cache_key = None

    def update_plot_bounds(self):
        self.bounds_revision += 1

    def _build_heatmaps(self, source_plots: Plots):
        heatmaps = []
        for plot_id, (x_data, y_data, count) in source_plots.items():
            sample_count = min(count, len(x_data), len(y_data))
            daily_values: dict[tuple[int, int, int], list[float]] = {}
            for timestamp, value in zip(
                    x_data[:sample_count],
                    y_data[:sample_count],
            ):
                if not np.isfinite(timestamp) or not np.isfinite(value):
                    continue
                sample_date = datetime.fromtimestamp(
                    float(timestamp),
                    tz=timezone.utc,
                ).date()
                daily_values.setdefault(
                    (sample_date.year, sample_date.month, sample_date.day),
                    [],
                ).append(float(value))

            years = sorted({day[0] for day in daily_values})
            for year in years:
                dates = [
                    date(year, month, day)
                    for sample_year, month, day in daily_values
                    if sample_year == year
                ]
                range_start = min(dates)
                range_end = max(dates)
                grid_start = range_start - timedelta(days=range_start.weekday())
                grid_end = range_end + timedelta(days=6 - range_end.weekday())
                week_count = (grid_end - grid_start).days // 7 + 1
                grid = np.full((7, week_count), np.nan, dtype=np.float64)
                for (sample_year, month, day), values in daily_values.items():
                    if sample_year != year:
                        continue
                    sample_date = date(year, month, day)
                    week = (sample_date - grid_start).days // 7
                    grid[sample_date.weekday(), week] = float(np.mean(values))

                title = self.source.raw_plot_title(plot_id)
                if len(years) > 1:
                    title = f"{title} ({year})"
                ticks, labels = _calendar_month_ticks(
                    grid_start,
                    range_start,
                    range_end,
                )
                heatmaps.append(CalendarHeatmapSeries(
                    plot_id=f"{plot_id}:{year}",
                    title=title,
                    year=year,
                    values=np.ascontiguousarray(grid),
                    start_date=grid_start,
                    month_ticks=ticks,
                    month_labels=labels,
                ))
        return tuple(heatmaps)

    def _update_scale(self):
        finite = [
            heatmap.values[np.isfinite(heatmap.values)]
            for heatmap in self._calendar_cache
        ]
        finite = [values for values in finite if len(values) > 0]
        if not finite:
            self.scale_min, self.scale_max = 0.0, 1.0
            return
        self.scale_min = min(float(values.min()) for values in finite)
        self.scale_max = max(float(values.max()) for values in finite)
        if self.scale_min == self.scale_max:
            padding = max(abs(self.scale_min) * 0.05, 0.5)
            self.scale_min -= padding
            self.scale_max += padding


def _calendar_month_ticks(
        grid_start: date,
        range_start: date,
        range_end: date,
):
    ticks = []
    labels = []
    current = date(range_start.year, range_start.month, 1)
    while current <= range_end:
        tick_date = max(current, range_start)
        ticks.append((tick_date - grid_start).days / 7 + 0.5)
        labels.append(calendar.month_abbr[current.month])
        next_month = current.month % 12 + 1
        next_year = current.year + current.month // 12
        current = date(next_year, next_month, 1)
    return tuple(ticks), tuple(labels)
