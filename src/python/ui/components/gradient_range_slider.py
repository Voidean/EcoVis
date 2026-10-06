import math

from imgui_bundle import imgui

from model.gradient import Gradient
from model.weather_type import WeatherType, ScalarWeatherType


def gradient_range_slider(
        start: float,
        end: float,
        label: str,
        gradient: Gradient,
        weather: WeatherType,
        *,
        height=20,
) -> tuple[float, float] | None:
    """Render the range widget and return an edited range, if any."""
    content_avail = imgui.get_content_region_avail()
    width = content_avail.x
    pos = imgui.get_cursor_screen_pos()  # Top-left of the widget
    draw_list = imgui.get_window_draw_list()

    # Reserve space for the widget
    imgui.invisible_button(label, (width, height + 40))
    is_active = imgui.is_item_active()

    v_start = start
    v_end = end
    edited_range = None

    # Convert 0.0-1.0 values to pixel offsets
    x_start = pos.x + (v_start * width)
    x_end = pos.x + (v_end * width)

    # Draw the segments
    def imgui_color(color):
        return imgui.get_color_u32((color[0] / 255, color[1] / 255, color[2] / 255, color[3] / 255))

    # Left clamped area
    draw_list.add_rect_filled((pos.x, pos.y + 20), (x_start, pos.y + 20 + height), imgui_color(gradient.color_start))
    # The Gradient Texture (rendered between knobs)
    draw_list.add_image(imgui.ImTextureRef(gradient.texture.get_id()), (x_start, pos.y + 20),
                        (x_end, pos.y + 20 + height))
    # Right clamped area
    draw_list.add_rect_filled((x_end, pos.y + 20), (pos.x + width, pos.y + 20 + height),
                              imgui_color(gradient.color_end))

    # Interaction Logic
    if is_active and imgui.is_mouse_dragging(0):
        # get_mouse_pos liefert ein ImVec2-Objekt
        mouse_x = imgui.get_mouse_pos().x
        # Calculate normalized value (0.0 to 1.0)
        new_val = (mouse_x - pos.x) / width
        new_val = max(0.0, min(1.0, new_val))  # Clamp to bounds

        # Determine which knob is closer to the mouse when starting the drag
        dist_start = abs(mouse_x - x_start)
        dist_end = abs(mouse_x - x_end)

        if dist_start < dist_end:
            if new_val <= v_end:  # Prevent crossing
                v_start = new_val
        else:
            if new_val >= v_start:  # Prevent crossing
                v_end = new_val
        edited_range = v_start, v_end

    # Draw Labels
    text_color = imgui.get_color_u32((1.0, 1.0, 1.0, 1.0))
    data_min = weather.data_min if isinstance(weather, ScalarWeatherType) else 0
    data_max = weather.data_max if isinstance(weather, ScalarWeatherType) else math.sqrt(2) * weather.data_max

    # Static Labels (Min/Max at the far edges)
    # Using draw_list to ensure they are inside the widget area
    # add_text verlangt die Position als ImVec2-Tupel
    draw_list.add_text((pos.x, pos.y + 5), text_color, f"{data_min:.4g}{weather.unit}")

    max_text = f"{data_max:.4g}{weather.unit}"
    max_text_width = imgui.calc_text_size(max_text).x
    draw_list.add_text((pos.x + width - max_text_width, pos.y + 5), text_color, max_text)

    # Dynamic Labels (Position relative to min/max)
    val_start = data_min + (v_start * (data_max - data_min))
    val_end = data_min + (v_end * (data_max - data_min))

    label_start = f"{val_start:.4g}{weather.unit}"
    label_end = f"{val_end:.4g}{weather.unit}"

    # Draw values slightly below the knobs
    label_start_x = max(pos.x, x_start - (imgui.calc_text_size(label_start).x / 2))
    label_end_x = min(pos.x + width - imgui.calc_text_size(label_end).x,
                      x_end - (imgui.calc_text_size(label_end).x / 2))

    draw_list.add_text((label_start_x, pos.y + height + 25), text_color, label_start)
    draw_list.add_text((label_end_x, pos.y + height + 25), text_color, label_end)

    # Draw Knobs (Last, so they stay on top)
    def draw_knob(draw_list, x, y, height):
        # Black outline for visibility
        draw_list.add_rect_filled((x - 3, y - 2), (x + 3, y + height + 2),
                                  imgui.get_color_u32((0.0, 0.0, 0.0, 1.0)))
        # White handle
        draw_list.add_rect_filled((x - 1, y - 2), (x + 1, y + height + 2),
                                  imgui.get_color_u32((1.0, 1.0, 1.0, 1.0)))

    draw_knob(draw_list, x_start, pos.y + 20, height)
    draw_knob(draw_list, x_end, pos.y + 20, height)
    return edited_range
