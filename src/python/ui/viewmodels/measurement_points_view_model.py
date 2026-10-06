from dataclasses import dataclass

from pyglm import glm

from model.geo_pos import GeoPos
from model.state.render_state import render_state
from model.weather_type import SYNC_SCALAR
from rendering.scene.camera import Camera
from ui.interactions.interaction_event import InteractionEvent, MouseEvent
from ui.interactions.interaction_manager import (
    EventListener,
    InteractionPriority,
    interaction_manager,
)
from ui.view_model import ViewModel
from util.coordinate_conversion import geo_pos_to_uv
from util.data_reading_util import get_data_read_out
from util.geo_projection import calculate_geo_pos_from_click
from util.input_constants import MouseButton
from util.screen_projection import world_space_to_screen_space


INTERACTION_RANGE = 10.0


@dataclass
class MeasurementPoint:
    pos: GeoPos

    def __post_init__(self):
        self.uv = geo_pos_to_uv(self.pos)


@dataclass(frozen=True)
class MeasurementPresentation:
    x: float
    y: float
    text: str
    hovered: bool


class MeasurementPointsViewModel(ViewModel, EventListener):
    def __init__(self, camera: Camera, data_textures=None):
        super().__init__()
        self.camera = camera
        self.data_textures = data_textures
        self.points: list[MeasurementPoint] = []
        self.context_point: MeasurementPoint | None = None
        self.open_context_menu = False
        interaction_manager.add_listener(self, InteractionPriority.DEFAULT)

    def presentations(self, mouse_pos):
        for point in self.points:
            screen_pos = self.get_screen_pos(point)
            if screen_pos is None:
                continue
            text = (
                f"Lon: {point.pos.lon_deg:.2f}°, "
                f"Lat: {point.pos.lat_deg:.2f}°\n"
            )
            if render_state.scalar_data_type and self.data_textures:
                scalar = (
                    render_state.vector_data_type
                    if render_state.scalar_data_type == SYNC_SCALAR
                    else render_state.scalar_data_type
                )
                text += get_data_read_out(
                    self.data_textures["scalar"].data,
                    point.uv,
                    scalar,
                )
            x, y = screen_pos
            yield MeasurementPresentation(
                x=x,
                y=y,
                text=text,
                hovered=(
                    glm.distance(screen_pos, glm.dvec2(mouse_pos))
                    < INTERACTION_RANGE
                ),
            )

    def take_context_menu_request(self) -> bool:
        requested = self.open_context_menu
        self.open_context_menu = False
        return requested

    def delete_context_point(self):
        if self.context_point in self.points:
            self.points.remove(self.context_point)
        self.context_point = None

    def delete_all(self):
        self.points.clear()
        self.context_point = None

    def handle_event(self, event: InteractionEvent):
        if not isinstance(event, MouseEvent):
            return
        if event.button == MouseButton.LEFT:
            geo_pos = calculate_geo_pos_from_click(
                event.world_pos,
                render_state.projection,
            )
            if geo_pos is None:
                return
            self.points.append(MeasurementPoint(geo_pos))
            event.consume()
        elif event.button == MouseButton.RIGHT:
            for point in self.points:
                screen_pos = self.get_screen_pos(point)
                if (
                        screen_pos is not None
                        and glm.distance(
                            screen_pos,
                            glm.dvec2(event.mouse_pos),
                        ) < INTERACTION_RANGE
                ):
                    self.context_point = point
                    self.open_context_menu = True
                    event.consume()
                    break

    def get_screen_pos(self, point: MeasurementPoint):
        world_pos = render_state.projection.project(point.pos)
        return world_space_to_screen_space(world_pos, self.camera)

    def destroy(self):
        if self.destroyed:
            return
        self.detach()
        self.points.clear()
        super().destroy()
