"""ImPlot calendar heatmap component."""

from typing import override

import numpy as np
from imgui_bundle import imgui, implot

from ui.components.base_component import ViewModelComponent
from ui.viewmodels.graph_display.calendar import CalendarHeatmapViewModel


class CalendarHeatmapContentComponent(
        ViewModelComponent[CalendarHeatmapViewModel]
):
    """Render each source series as an aligned calendar small multiple."""

    _weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    @override
    def render(self):
        view_model = self.view_model
        heatmaps = view_model.heatmaps()
        if not heatmaps:
            imgui.text(
                "Loading data..." if view_model.loading else "No data to display."
            )
            return

        imgui.text(f"Cell value: daily mean of {view_model.label_y}")
        axes_flags = (
            implot.AxisFlags_.lock
            | implot.AxisFlags_.no_grid_lines
            | implot.AxisFlags_.no_tick_marks
        )
        implot.push_colormap(implot.Colormap_.viridis)
        try:
            for heatmap in heatmaps:
                imgui.push_id(heatmap.plot_id)
                week_count = heatmap.values.shape[1]
                available_width = imgui.get_content_region_avail().x
                plot_width = max(220.0, available_width - 72.0)
                if implot.begin_plot(
                        f"{heatmap.title}##calendar_{self.instance_id}",
                        size=(plot_width, 180.0),
                        flags=implot.Flags_.no_legend,
                ):
                    implot.setup_axes(
                        "Calendar week",
                        "",
                        axes_flags,
                        axes_flags,
                    )
                    implot.setup_axes_limits(
                        0.0,
                        float(week_count),
                        0.0,
                        7.0,
                        imgui.Cond_.always,
                    )
                    implot.setup_axis_ticks(
                        implot.ImAxis_.x1,
                        heatmap.month_ticks,
                        heatmap.month_labels,
                        False,
                    )
                    implot.setup_axis_ticks(
                        implot.ImAxis_.y1,
                        6.5,
                        0.5,
                        7,
                        self._weekdays,
                        False,
                    )
                    implot.plot_heatmap(
                        heatmap.title,
                        np.nan_to_num(
                            heatmap.values,
                            nan=view_model.scale_min,
                        ),
                        scale_min=view_model.scale_min,
                        scale_max=view_model.scale_max,
                        label_fmt="",
                        bounds_min=implot.Point(0.0, 0.0),
                        bounds_max=implot.Point(float(week_count), 7.0),
                    )
                    self._draw_missing_cells(heatmap.values)
                    implot.end_plot()
                imgui.same_line()
                implot.colormap_scale(
                    f"##calendar_scale_{self.instance_id}",
                    view_model.scale_min,
                    view_model.scale_max,
                    size=(60.0, 180.0),
                    format="%g",
                )
                imgui.pop_id()
        finally:
            implot.pop_colormap()

    @staticmethod
    def _draw_missing_cells(values: np.ndarray):
        missing_color = imgui.get_color_u32((0.08, 0.08, 0.08, 1.0))
        draw_list = implot.get_plot_draw_list()
        for row, column in np.argwhere(~np.isfinite(values)):
            upper_left = implot.plot_to_pixels(float(column), float(7 - row))
            lower_right = implot.plot_to_pixels(
                float(column + 1),
                float(6 - row),
            )
            draw_list.add_rect_filled(
                (
                    min(upper_left.x, lower_right.x) + 0.5,
                    min(upper_left.y, lower_right.y) + 0.5,
                ),
                (
                    max(upper_left.x, lower_right.x) - 0.5,
                    max(upper_left.y, lower_right.y) - 0.5,
                ),
                missing_color,
            )
