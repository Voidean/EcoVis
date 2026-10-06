"""Shared ImPlot frame and standard graph representation components."""

from typing import override

from imgui_bundle import imgui, implot

from ui.components.base_component import ViewModelComponent
from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from ui.viewmodels.graph_display.frequency import ScatterViewModel, HistogramViewModel
from util.plotting_util import plot, render_plot_series, setup_time_plot


class GraphDisplayComponent(ViewModelComponent[GraphDisplayViewModel]):
    """Shared plot frame; subclasses only select their ImPlot primitive."""

    render_kind = "line"

    def __init__(self, view_model: GraphDisplayViewModel):
        super().__init__(view_model)
        self._applied_bounds_revision = -1

    @override
    def render(self):
        self.render_options()
        view_model = self.view_model
        visible_plots = view_model.visible_plots()
        if (
                not visible_plots
                and not view_model.loading
                and view_model.empty_message
        ):
            imgui.text(view_model.empty_message)
            return
        plot(
            data=visible_plots,
            label=(
                f"{view_model.label} ({view_model.display_name})"
                f"##graph_display_{self.instance_id}"
            ),
            label_x=view_model.label_x,
            label_y=view_model.label_y,
            apply_settings=self._apply_graph_settings,
            get_title=view_model.visible_plot_title,
            highlight_key=view_model.highlighted,
            loading=view_model.loading,
            render_series=self._render_series,
        )
        if imgui.button(
                f"Normalize Plot Bounds##graph_display_{self.instance_id}"
        ):
            view_model.update_plot_bounds()

    def render_options(self):
        view_model = self.view_model
        if view_model.supports_ignore_zeros:
            changed, ignore = imgui.checkbox(
                (
                    f"Ignore zero values ({view_model.zero_share:.1%} zero)"
                    f"##ignore_zeros_{self.instance_id}"
                ),
                view_model.ignore_zero_values,
            )
            if changed:
                view_model.set_ignore_zero_values(ignore)

    def _render_series(self, key, title, x_data, y_data, spec):
        render_plot_series(
            self.render_kind,
            key,
            title,
            x_data,
            y_data,
            spec,
            bar_width=self.view_model.bar_width,
        )

    def _apply_graph_settings(self):
        view_model = self.view_model
        apply_limits = (
            self._applied_bounds_revision != view_model.bounds_revision
        )
        if view_model.uses_time_axis:
            setup_time_plot(view_model.graph_bounds, apply_limits)
        else:
            implot.setup_axis_scale(implot.ImAxis_.x1, implot.Scale_.linear)
            if apply_limits:
                implot.setup_axes_limits(
                    view_model.graph_bounds["x_min"],
                    view_model.graph_bounds["x_max"],
                    view_model.graph_bounds["y_min"],
                    view_model.graph_bounds["y_max"],
                    imgui.Cond_.always,
                )
        self._applied_bounds_revision = view_model.bounds_revision


class TimeSeriesContentComponent(GraphDisplayComponent):
    render_kind = "line"


class ScatterContentComponent(GraphDisplayComponent):
    render_kind = "scatter"
    view_model: ScatterViewModel

    @override
    def render_options(self):
        super().render_options()
        imgui.set_next_item_width(220.0)
        changed, bin_count = imgui.slider_int(
            f"Bins##scatter_bins_{self.instance_id}",
            self.view_model.bin_count,
            5,
            100,
        )
        if changed:
            self.view_model.set_bin_count(bin_count)


class AreaContentComponent(GraphDisplayComponent):
    render_kind = "area"


class CumulativeYieldContentComponent(GraphDisplayComponent):
    render_kind = "line"


class DistributionContentComponent(GraphDisplayComponent):
    render_kind = "line"


class HistogramContentComponent(GraphDisplayComponent):
    render_kind = "bars"
    view_model: HistogramViewModel

    @override
    def render_options(self):
        super().render_options()
        imgui.set_next_item_width(220.0)
        changed, bin_count = imgui.slider_int(
            f"Bins##histogram_bins_{self.instance_id}",
            self.view_model.bin_count,
            5,
            100,
        )
        if changed:
            self.view_model.set_bin_count(bin_count)
