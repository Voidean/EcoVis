from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot


def setup_time_plot(bounds: dict[str, float], apply_limits: bool):
    """Apply the time-axis settings shared by all time-series graphs."""
    implot.get_style().use24_hour_clock = True
    implot.get_style().use_iso8601 = True
    implot.setup_axis_scale(0, implot.Scale_.time)
    if apply_limits:
        implot.setup_axes_limits(
            bounds["x_min"],
            bounds["x_max"],
            bounds["y_min"],
            bounds["y_max"],
            imgui.Cond_.always,
        )


def plot(
        data: dict[str, tuple[np.ndarray, np.ndarray, float]],
        label: str,
        label_x: str = "",
        label_y: str = "",
        apply_settings=lambda: None,
        get_title=lambda x: str(x),
        highlight_key: str = None,
        loading: bool = False,
        get_y_axis=lambda _: implot.ImAxis_.y1,
        render_series: Callable | None = None,
):
    if implot.begin_plot(label, size=(-1.0, 350.0)):
        implot.setup_axes(label_x, label_y)

        apply_settings()

        for key, (x_array, y_array, count) in data.items():
            if count > 0:
                implot.set_axes(implot.ImAxis_.x1, get_y_axis(key))
                is_highlighted = (str(key) == str(highlight_key))

                spec = implot.Spec()
                if is_highlighted:
                    spec.line_weight = 4.0

                title = get_title(key)
                if render_series is None:
                    render_plot_series(
                        "line", key, title, x_array, y_array, spec,
                    )
                else:
                    render_series(key, title, x_array, y_array, spec)

        if loading:
            plot_pos = implot.get_plot_pos()
            plot_size = implot.get_plot_size()
            draw_list = implot.get_plot_draw_list()
            overlay_color = imgui.get_color_u32((0.05, 0.05, 0.05, 0.72))
            text_color = imgui.get_color_u32((1.0, 1.0, 1.0, 1.0))
            draw_list.add_rect_filled(
                plot_pos,
                (plot_pos.x + plot_size.x, plot_pos.y + plot_size.y),
                overlay_color,
            )
            text = "Loading data..."
            text_size = imgui.calc_text_size(text)
            draw_list.add_text(
                (plot_pos.x + (plot_size.x - text_size.x) / 2,
                 plot_pos.y + (plot_size.y - text_size.y) / 2),
                text_color,
                text,
            )


        implot.end_plot()


def render_plot_series(
        render_kind: str,
        _,
        title: str,
        x_array: np.ndarray,
        y_array: np.ndarray,
        spec: implot.Spec,
        *,
        bar_width: float | None = None,
):
    """Render one prepared series using a small set of ImPlot primitives."""
    if render_kind == "bars":
        spec.fill_alpha = 0.8
        implot.plot_bars(
            title,
            xs=x_array,
            ys=y_array,
            bar_size=bar_width or 0.67,
            spec=spec,
        )
    elif render_kind == "scatter":
        implot.plot_scatter(title, xs=x_array, ys=y_array, spec=spec)
    elif render_kind == "area":
        spec.fill_alpha = 0.65
        implot.plot_shaded(
            title,
            xs=x_array,
            ys=y_array,
            yref=0.0,
            spec=spec,
        )
    else:
        implot.plot_line(title, xs=x_array, ys=y_array, spec=spec)

def convert_datetime_arrays_to_plot(timestamps, values):
    """Convert datetime and value arrays into one ImPlot series."""
    x_timestamps = np.ascontiguousarray(np.asarray(
        [float(timestamp.timestamp()) for timestamp in timestamps],
        dtype=np.float64,
    ).reshape(-1))
    y_values = np.ascontiguousarray(
        np.asarray(values, dtype=np.float64).reshape(-1)
    )
    count = min(len(x_timestamps), len(y_values))
    return x_timestamps[:count], y_values[:count], count
