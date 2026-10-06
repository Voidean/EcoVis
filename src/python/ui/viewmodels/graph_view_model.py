import calendar
import logging
from abc import abstractmethod

from model.data_requests import GraphPlotRequest
from model.state.time_state import time_state
from service.data_streamer import AsyncDataLoader
from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from ui.viewmodels.graph_display.calendar import CalendarHeatmapViewModel
from ui.viewmodels.graph_display.distributions import WeibullViewModel, BetaViewModel
from ui.viewmodels.graph_display.frequency import ScatterViewModel, HistogramViewModel
from ui.viewmodels.graph_display.time_series import TimeSeriesViewModel, AreaViewModel, MeanSquaredErrorViewModel
from ui.viewmodels.plot_view_model import Plots, PlotViewModel
from ui.viewmodels.sync_view_model import SyncViewModel


logger = logging.getLogger(__name__)


class GraphViewModel(PlotViewModel, SyncViewModel):
    """Application logic for asynchronously loaded time-series graphs."""

    def __init__(self):
        PlotViewModel.__init__(self)
        SyncViewModel.__init__(self)

        start_time = time_state.current_time.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        next_month = start_time.month % 12 + 1
        next_year = start_time.year + (start_time.month // 12)
        next_day = min(
            start_time.day,
            calendar.monthrange(next_year, next_month)[1],
        )
        self.start_time = start_time
        self.end_time = start_time.replace(
            year=next_year,
            month=next_month,
            day=next_day,
        )
        self.applied_start_time = self.start_time
        self.applied_end_time = self.end_time

        self.plot_view = "Time series"
        self.plot_views: list[str] = []
        self._display_view_models: dict[str, GraphDisplayViewModel] = {}
        self.add_plot_view(TimeSeriesViewModel(self))
        self.add_plot_view(ScatterViewModel(self))
        self.add_plot_view(AreaViewModel(self))
        self.add_plot_view(MeanSquaredErrorViewModel(self))
        self.add_plot_view(HistogramViewModel(self))
        self.add_plot_view(CalendarHeatmapViewModel(self))
        self.add_plot_view(WeibullViewModel(self))
        self.add_plot_view(BetaViewModel(self))
        self.date_precision = ["Year", "Month", "Day", "Hour"]
        self.years_prior = 0
        self.sync_mode = "Time and Location"
        self.sync_options = ["Time", "Location", "Time and Location"]
        self.display_name = "Graph"

        self.render_datepicker = True
        self.render_individual_datepicker = True
        self._plot_loader = AsyncDataLoader[GraphPlotRequest, Plots](
            self._load_plot_request,
            thread_name_prefix="GraphData",
        )

    @property
    def revision(self) -> tuple:
        return (
            self.plot_view,
            self.active_display_view_model.revision,
        )

    @property
    def raw_data_revision(self) -> tuple:
        """Revision of loaded/filter state, independent of its presentation."""
        return (
            self._plots_revision,
            self._display_revision_token(),
            self.label_y,
        )

    @property
    def display_view_models(self) -> tuple[GraphDisplayViewModel, ...]:
        return tuple(self._display_view_models.values())

    @property
    def mergeable_plot_views(self) -> tuple[str, ...]:
        """Views that can be rendered together on one set of plot axes."""
        return tuple(
            view.display_name
            for view in self.display_view_models
            if view.merge_supported
        )

    @property
    def active_display_view_model(self) -> GraphDisplayViewModel:
        return self._display_view_models[self.plot_view]

    @property
    def uses_time_axis(self) -> bool:
        return self.active_display_view_model.uses_time_axis

    @property
    def x_axis_key(self) -> tuple[str, str]:
        return self.active_display_view_model.x_axis_key

    @property
    def x_axis_label(self) -> str:
        return self.active_display_view_model.label_x

    @property
    def plot_y_label(self) -> str:
        return self.active_display_view_model.plot_y_label

    @property
    def render_kind(self) -> str:
        return self.active_display_view_model.render_kind

    @property
    def bar_width(self) -> float | None:
        return self.active_display_view_model.bar_width

    @property
    def merge_supported(self) -> bool:
        return self.active_display_view_model.merge_supported

    def tick(self):
        if self.destroyed:
            return
        self._poll_plot_load()
        self._refresh_derived_state()
        self.active_display_view_model.tick()
        if self.changed:
            self.changed = False
            self.applied_start_time = self.start_time
            self.applied_end_time = self.end_time
            self.reload_plot()
            self.update_links()

    def update(
            self,
            start_time=None,
            end_time=None,
            plot_view=None,
            years_prior=None,
            **_,
    ):
        if start_time is not None and start_time != self.start_time:
            self.start_time = start_time
            self.changed = True
        if end_time is not None and end_time != self.end_time:
            self.end_time = end_time
            self.changed = True
        if plot_view is not None:
            self.set_plot_view(plot_view)
        if years_prior is not None:
            self.set_years_prior(years_prior)

    def set_plot_view(self, plot_view: str):
        if plot_view == self.plot_view or plot_view not in self.plot_views:
            return
        self.plot_view = plot_view
        self.update_plot_bounds()

    def add_plot_view(self, view_model: GraphDisplayViewModel):
        """Register one local representation without touching loaded data."""
        name = view_model.display_name
        if name in self._display_view_models:
            raise ValueError(f"Duplicate graph view: {name}")
        self._display_view_models[name] = view_model
        self.plot_views.append(name)

    def set_years_prior(self, years_prior: int):
        years_prior = min(max(0, years_prior), 20)
        if years_prior != self.years_prior:
            self.years_prior = years_prior
            self.changed = True

    def request_reload(self):
        self.changed = True

    def set_sync_mode(self, sync_mode: str):
        if sync_mode == self.sync_mode:
            return
        self.sync_mode = sync_mode
        if self.host:
            self.sync()
        self.changed = True

    def visible_plots(self) -> Plots:
        return self.active_display_view_model.visible_plots()

    def displayed_plots(self) -> Plots:
        return self.plots

    def visible_plot_title(self, plot_id) -> str:
        return self.active_display_view_model.visible_plot_title(plot_id)

    def raw_plot_title(self, plot_id) -> str:
        return self.get_title(plot_id)

    def set_plots(self, plots: Plots):
        self._invalidate_visible_plots()
        super().set_plots(plots)

    def update_plot_bounds(self):
        self.active_display_view_model.update_plot_bounds()

    def _submit_plot_load(self, request: GraphPlotRequest):
        self._plot_loader.submit(request)
        self.loading = True
        self.error = None

    def _poll_plot_load(self):
        outcome = self._plot_loader.update()
        if outcome is None:
            return

        self.loading = False
        if outcome.error is not None:
            self.error = outcome.error
            logger.error(
                "Failed to load graph data: %s",
                outcome.error,
                exc_info=(
                    type(outcome.error),
                    outcome.error,
                    outcome.error.__traceback__,
                ),
            )
            return

        self._apply_plot_load_result(outcome.value)

    def _apply_plot_load_result(self, result):
        """Apply a successful loader result; subclasses may add derived state."""
        self.set_plots(result or {})

    def _refresh_derived_state(self):
        self.render_datepicker = not self.host or "Time" not in self.sync_mode

    def _display_revision_token(self) -> tuple:
        return ()

    def _invalidate_visible_plots(self):
        for view_model in self.display_view_models:
            view_model.invalidate()

    def distribution_maximum(self, plot_id, values):
        return self._distribution_maximum(plot_id, values)

    @staticmethod
    def _distribution_maximum(_, values):
        return values.max()

    @abstractmethod
    def reload_plot(self):
        pass

    @abstractmethod
    def _load_plot_request(self, request: GraphPlotRequest) -> Plots:
        pass

    def destroy(self):
        if self.destroyed:
            return
        self._plot_loader.shutdown()
        for view_model in self.display_view_models:
            view_model.destroy()
        self._display_view_models.clear()
        self.plot_views.clear()
        self.destroy_sync()
        PlotViewModel.destroy(self)
