from imgui_bundle import imgui

from rendering.scene.camera import Camera
from ui.components.base_component import ViewModelComponent
from ui.viewmodels.measurement_points_view_model import MeasurementPoint, MeasurementPointsViewModel


def draw_outlined_text(x, y, color, outline_color, text):
    draw_list = imgui.get_background_draw_list()
    draw_list.add_text((x + 1, y), outline_color, text)
    draw_list.add_text((x - 1, y), outline_color, text)
    draw_list.add_text((x, y + 1), outline_color, text)
    draw_list.add_text((x, y - 1), outline_color, text)
    draw_list.add_text((x, y), color, text)


class MeasurementPoints(ViewModelComponent[MeasurementPointsViewModel]):
    def __init__(
            self,
            camera: Camera,
            data_textures=None,
            view_model: MeasurementPointsViewModel | None = None,
    ):
        super().__init__(
            view_model or MeasurementPointsViewModel(camera, data_textures)
        )

    def render(self, mouse_pos):
        vm = self.view_model
        self.prepare_render()
        black = imgui.get_color_u32((0.0, 0.0, 0.0, 1.0))
        for point in vm.presentations(mouse_pos):
            color = imgui.get_color_u32(
                (1.0, 1.0, 0.5, 1.0)
                if point.hovered
                else (1.0, 1.0, 1.0, 1.0)
            )
            draw_list = imgui.get_background_draw_list()
            draw_list.add_circle_filled((point.x, point.y), 5, black)
            draw_list.add_circle_filled((point.x, point.y), 3, color)
            draw_outlined_text(
                point.x + 10,
                point.y + 6,
                color,
                black,
                point.text,
            )

        if vm.take_context_menu_request():
            imgui.open_popup("mp_context_menu")
        if imgui.begin_popup("mp_context_menu"):
            if imgui.menu_item("Delete this Marker", "", False, True)[0]:
                vm.delete_context_point()
            if imgui.menu_item("Delete all Markers", "", False, True)[0]:
                vm.delete_all()
            imgui.end_popup()

    def get_screen_pos(self, point: MeasurementPoint):
        return self.view_model.get_screen_pos(point)
