from collections.abc import Sequence
from typing import cast, override

from imgui_bundle import imgui, implot

from ui.components.base_component import Component
from ui.components.composite_component import CompositeComponent
from ui.components.data_controls_component import DataComponentControls
from ui.components.graph_component_base import GraphComponent
from ui.viewmodels.graph_display.frequency import ScatterViewModel, HistogramViewModel
from ui.viewmodels.merged_graph_view_model import (
    MergedGraphViewModel,
    MergedPlotSnapshot,
)
from ui.viewmodels.plot_view_model import PlotViewModel
from util.plotting_util import plot, render_plot_series, setup_time_plot


class MergedGraphComponent(CompositeComponent):
    """Composable merged plot retaining its independent child graphs."""

    def __init__(self, components: Sequence[GraphComponent]):
        if len(components) < 2:
            raise ValueError("A merged graph requires at least two graph components")
        if any(not isinstance(component, GraphComponent) for component in components):
            raise TypeError("Merged graphs can only contain graph components")
        super().__init__(components)
        self.view_model = MergedGraphViewModel(
            [component.view_model for component in self.graphs]
        )
        self.state = self.view_model
        self._controllers = tuple(
            DataComponentControls(graph)
            for graph in self.graphs
        )
        self.graph_bounds = {}
        self.axis_bounds = {}
        self.axis_labels = {}
        self.plot_axes = {}
        self._apply_bounds = True
        self._plot_signature: tuple | None = None
        self._snapshot: MergedPlotSnapshot | None = None

    @property
    def display_name(self) -> str:
        return f"Merged Graph ({len(self.graphs)})"

    @property
    def graphs(self) -> tuple[GraphComponent, ...]:
        # Construction validates every child, and membership is immutable
        # until the entire composition is released.
        return cast(tuple[GraphComponent, ...], tuple(self._components))

    @override
    def render(self):
        self.view_model.tick()
        for index, (graph, controls) in enumerate(
                zip(self.graphs, self._controllers),
                start=1,
        ):
            imgui.push_id(f"graph_{id(graph)}")
            if imgui.collapsing_header(
                f"{graph.display_name} {index}##controls",
                imgui.TreeNodeFlags_.default_open,
            ):
                controls.render()
                graph.render_configuration(show_view_selector=False)
            imgui.pop_id()

        imgui.spacing()
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        imgui.spacing()
        self._combo_control(
            "View",
            self.view_model.plot_views,
            self.view_model.plot_view,
            self.view_model.set_plot_view,
        )
        self._render_display_options()

        snapshot = self.view_model.snapshot()
        self._snapshot = snapshot
        if snapshot.signature != self._plot_signature:
            self._rebuild_plot_layout(snapshot)

        if snapshot.unsupported_views:
            imgui.text(
                "This view uses its own layout and cannot be drawn on a "
                "merged axis:"
            )
            for view in snapshot.unsupported_views:
                imgui.bullet_text(view)
            return
        if snapshot.incompatible_x_axes:
            imgui.text(
                "Merged graphs use one X axis; choose compatible views "
                "and units for every graph."
            )
            return

        labels_y = self.axis_labels.get(implot.ImAxis_.y1, "")
        plot(
            data=snapshot.plots,
            label=f"Merged Graph##{self.instance_id}",
            label_x=snapshot.x_axis_label,
            label_y=labels_y,
            apply_settings=self._apply_graph_settings,
            get_title=lambda key: snapshot.titles[key],
            highlight_key=snapshot.highlighted,
            loading=snapshot.loading,
            get_y_axis=lambda key: self.plot_axes.get(
                key,
                implot.ImAxis_.y1,
            ),
            render_series=lambda key, title, x_data, y_data, spec: (
                render_plot_series(
                    snapshot.render_kinds[key],
                    key,
                    title,
                    x_data,
                    y_data,
                    spec,
                    bar_width=snapshot.bar_widths[key],
                )
            ),
        )
        if imgui.button(f"Normalize Plot Bounds##merged_{self.instance_id}"):
            self._rebuild_bounds(snapshot)

    def _render_display_options(self):
        display = self.view_model.active_display_view_model
        if display.supports_ignore_zeros:
            changed, ignore = imgui.checkbox(
                (
                    f"Ignore zero values ({display.zero_share:.1%} zero)"
                    f"##merged_ignore_zeros_{self.instance_id}"
                ),
                display.ignore_zero_values,
            )
            if changed:
                display.set_ignore_zero_values(ignore)

        if isinstance(display, (ScatterViewModel, HistogramViewModel)):
            imgui.set_next_item_width(220.0)
            changed, bin_count = imgui.slider_int(
                f"Bins##merged_bins_{self.instance_id}",
                display.bin_count,
                5,
                100,
            )
            if changed:
                display.set_bin_count(bin_count)

    def _rebuild_plot_layout(self, snapshot: MergedPlotSnapshot):
        self.plot_axes, self.axis_labels = self._assign_axes(snapshot.units)
        self._rebuild_bounds(snapshot)
        self._plot_signature = snapshot.signature

    def _rebuild_bounds(self, snapshot: MergedPlotSnapshot):
        self.graph_bounds = PlotViewModel.calculate_plot_bounds(snapshot.plots)
        plots_by_axis = {}
        for key, plot_data in snapshot.plots.items():
            axis = self.plot_axes.get(key, implot.ImAxis_.y1)
            plots_by_axis.setdefault(axis, {})[key] = plot_data
        self.axis_bounds = {
            axis: PlotViewModel.calculate_plot_bounds(plots)
            for axis, plots in plots_by_axis.items()
        }
        self._apply_bounds = True

    @staticmethod
    def _assign_axes(units):
        unit_axes = {}
        axis_units = {}
        available_axes = (
            implot.ImAxis_.y1,
            implot.ImAxis_.y2,
            implot.ImAxis_.y3,
        )
        for unit in dict.fromkeys(units.values()):
            axis = available_axes[min(len(unit_axes), len(available_axes) - 1)]
            unit_axes[unit] = axis
            axis_units.setdefault(axis, []).append(unit)
        return (
            {key: unit_axes[unit] for key, unit in units.items()},
            {axis: " / ".join(names) for axis, names in axis_units.items()},
        )

    def _apply_graph_settings(self):
        snapshot = self._snapshot
        if snapshot is None:
            return
        if snapshot.uses_time_axis:
            setup_time_plot(self.graph_bounds, False)
        else:
            implot.setup_axis_scale(implot.ImAxis_.x1, implot.Scale_.linear)

        for axis, label in self.axis_labels.items():
            if axis != implot.ImAxis_.y1:
                implot.setup_axis(axis, label, implot.AxisFlags_.aux_default)

        if self._apply_bounds:
            implot.setup_axis_limits(
                implot.ImAxis_.x1,
                self.graph_bounds["x_min"],
                self.graph_bounds["x_max"],
                imgui.Cond_.always,
            )
            for axis, bounds in self.axis_bounds.items():
                implot.setup_axis_limits(
                    axis,
                    bounds["y_min"],
                    bounds["y_max"],
                    imgui.Cond_.always,
                )
        self._apply_bounds = False

    @override
    def hide(self):
        for controller in self._controllers:
            controller.hide()
        super().hide()

    @override
    def release_components(self) -> list[Component]:
        self._destroy_controllers()
        self.view_model.destroy()
        return super().release_components()

    @override
    def destroy(self):
        self._destroy_controllers()
        self.view_model.destroy()
        super().destroy()

    def _destroy_controllers(self):
        for controller in self._controllers:
            controller.destroy()
        self._controllers = ()
