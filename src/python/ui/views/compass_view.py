import math

from imgui_bundle import imgui

from rendering.scene.camera import Camera
from ui.viewmodels.compass_view_model import CompassViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewId, ViewMetadata


class CompassView(View[CompassViewModel]):
    def __init__(self, view_model: CompassViewModel | None = None):
        super().__init__(
            ViewMetadata(ViewId.COMPASS, "Compass"),
            view_model or CompassViewModel(),
        )

    def render(self, camera: Camera):
        self.view_model.set_camera(camera)
        self.prepare_render()
        _render_compass(self.view_model)


def _render_compass(view_model: CompassViewModel):
    """
    Renders vector compass overlay in the bottom-right corner.
    """
    radius = 50.0
    padding = 20.0

    heading = view_model.heading
    surface_scale = view_model.surface_scale
    compass_underside = view_model.underside

    io = imgui.get_io()
    window_pos = (io.display_size.x - radius - padding, io.display_size.y - radius - padding)

    imgui.set_next_window_pos(imgui.ImVec2(window_pos[0] - radius, window_pos[1] - radius))
    imgui.set_next_window_size(imgui.ImVec2(radius * 2, radius * 2))

    window_flags = (
            imgui.WindowFlags_.no_decoration |
            imgui.WindowFlags_.no_background |
            imgui.WindowFlags_.no_saved_settings
    )

    if imgui.begin("##CompassOverlay", None, window_flags):
        draw_list = imgui.get_window_draw_list()
        center = imgui.ImVec2(window_pos[0], window_pos[1])

        # Place an invisible button over the square bounds of the compass
        imgui.set_cursor_screen_pos(imgui.ImVec2(center.x - radius, center.y - radius))
        imgui.invisible_button("compass_hitbox", imgui.ImVec2(radius * 2, radius * 2))

        # Enforce strict circular hover (ignore the corners of the square button)
        mouse_pos = io.mouse_pos
        dist_sq = (mouse_pos.x - center.x) ** 2 + (mouse_pos.y - center.y) ** 2
        is_circular_hover = imgui.is_item_hovered() and (dist_sq <= radius ** 2)

        if is_circular_hover and imgui.is_item_clicked(0):
            view_model.snap_to_north()

        color_north_text = imgui.get_color_u32((1.0, 0.3, 0.3, 1.0))
        color_needle_north = imgui.get_color_u32((0.9, 0.2, 0.2, 1.0))
        color_ring = imgui.get_color_u32((1.0, 1.0, 1.0, 0.3))

        if compass_underside:
            color_cardinal = imgui.get_color_u32((1.0, 1.0, 1.0, 0.45))
            color_needle_south = imgui.get_color_u32((0.8, 0.8, 0.8, 0.45))
            color_surface_ring = imgui.get_color_u32((1.0, 1.0, 1.0, 0.275))
        else:
            color_cardinal = imgui.get_color_u32((1.0, 1.0, 1.0, 0.9))
            color_needle_south = imgui.get_color_u32((0.8, 0.8, 0.8, 0.9))
            color_surface_ring = imgui.get_color_u32((1.0, 1.0, 1.0, 0.55))

        # Background based on hover state
        if is_circular_hover:
            color_bg = imgui.get_color_u32((0.3, 0.3, 0.3, 0.7))  # Highlighted
        else:
            color_bg = imgui.get_color_u32((0.0, 0.0, 0.0, 0.5))  # Normal

        draw_list.add_circle_filled(center, radius - 1, color_bg, num_segments=32)

        # Outer subtle guiding ring
        draw_list.add_circle(center, radius - 3.5, color_ring, num_segments=32, thickness=1.5)

        # This inner ring and everything placed on it represent the horizontal
        # surface. Orthographic projection only foreshortens its vertical axis.
        surface_radius = radius - 8.0
        draw_list.add_ellipse(
            center,
            imgui.ImVec2(surface_radius, surface_radius * surface_scale),
            color_surface_ring,
            num_segments=32,
            thickness=1.25,
        )

        def surface_point(angle: float, distance: float) -> imgui.ImVec2:
            return imgui.ImVec2(
                center.x + math.sin(angle) * distance,
                center.y - math.cos(angle) * distance * surface_scale,
            )

        labels = [("N", 0.0, color_north_text), ("E", math.pi / 2, color_cardinal),
                  ("S", math.pi, color_cardinal), ("W", -math.pi / 2, color_cardinal)]

        for text, angle_offset, color in labels:
            total_angle = heading + angle_offset

            label_center = surface_point(total_angle, radius - 14.0)

            text_size = imgui.calc_text_size(text)
            text_pos = imgui.ImVec2(
                label_center.x - text_size.x * 0.5,
                label_center.y - text_size.y * 0.5
            )
            draw_list.add_text(text_pos, color, text)

            # Indicator ticks for major points
            tick_start = surface_point(total_angle, surface_radius)
            tick_end = surface_point(total_angle, surface_radius + 5.0)
            draw_list.add_line(tick_start, tick_end, color, thickness=1.5)

        # Compass Needle
        needle_radius = radius - 20.0
        angle_n = heading
        angle_s = heading + math.pi

        # Central wide base points for the needle polygons
        base_left = surface_point(angle_n - math.pi / 2, 7.5)
        base_right = surface_point(angle_n + math.pi / 2, 7.5)

        # North-pointing tip
        tip_n = surface_point(angle_n, needle_radius)
        draw_list.add_triangle_filled(tip_n, base_left, base_right, color_needle_north)

        # South-pointing tip
        tip_s = surface_point(angle_s, needle_radius)
        draw_list.add_triangle_filled(tip_s, base_right, base_left, color_needle_south)

    imgui.end()
