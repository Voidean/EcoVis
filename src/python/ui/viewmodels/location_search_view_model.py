import math

from pyglm import glm

from model.geo_pos import GeoPos
from model.projection import Projection
from model.state.render_state import render_state
from rendering.scene.camera import Camera
from rendering.scene.entity import Entity
from service.camera_flight import CameraFlight
from service.location_search import (
    Location,
    LocationSearchService,
    camera_altitude_for_location,
)
from ui.view_model import ViewModel
from util.coordinate_constants import GLOBE_RADIUS


MIN_SEARCH_LENGTH = 2


class LocationSearchViewModel(ViewModel):
    def __init__(
            self,
            service: LocationSearchService | None = None,
            camera_flight: CameraFlight | None = None,
    ):
        super().__init__()
        self.service = service or LocationSearchService()
        self.query = ""
        self.locations: tuple[Location, ...] = ()
        self.error: str | None = None
        self.loading = False
        self.selected_index = 0
        self.generation = 0
        self.camera_flight = camera_flight

    @property
    def can_search(self) -> bool:
        return len(self.query.strip()) >= MIN_SEARCH_LENGTH

    def tick(self):
        outcome = self.service.poll()
        if outcome is None or outcome.generation != self.generation:
            return
        self.locations = outcome.locations
        self.error = outcome.error
        self.loading = False
        self.selected_index = min(
            self.selected_index,
            max(0, len(self.locations) - 1),
        )

    def search(self, query: str, camera: Camera):
        self.query = query
        self.selected_index = 0
        self.locations = ()
        self.error = None
        self.loading = self.can_search
        camera_location = render_state.projection.unproject(camera.translation)
        self.generation = self.service.search(
            query,
            (camera_location.lat_deg, camera_location.lon_deg),
        )

    def move_selection(self, offset: int):
        if self.locations:
            self.selected_index = (
                self.selected_index + offset
            ) % len(self.locations)

    @property
    def selected_location(self) -> Location | None:
        if not self.locations:
            return None
        return self.locations[self.selected_index]

    def select_location(self, location: Location):
        self._move_camera(location)
        self.query = location.label

    def _move_camera(self, location: Location):
        if self.camera_flight is None:
            self.error = "Camera movement is not available yet"
            return

        projection = render_state.projection
        geo_position = GeoPos.from_degrees(
            location.longitude,
            location.latitude,
        )
        target = projection.project(geo_position)
        altitude = camera_altitude_for_location(location)
        target_camera = Entity()

        if projection == Projection.GLOBE:
            target_up = glm.normalize(target)
            target_translation = target_up * (GLOBE_RADIUS + altitude)
            north = glm.dvec3(
                -math.sin(geo_position.lat) * math.sin(geo_position.lon),
                math.sin(geo_position.lat) * math.cos(geo_position.lon),
                math.cos(geo_position.lat),
            )
            target_camera.translation = target_translation
            target_camera.turn_to_vector(
                target - target_translation,
                world_up=north,
            )
        else:
            target_translation = glm.dvec3(target.x, target.y, altitude)
            target_camera.translation = target_translation
            target_camera.turn_to_vector(
                target - target_translation,
                world_up=glm.dvec3(0.0, 1.0, 0.0),
            )

        self.camera_flight.start(
            target_translation,
            target_camera.rotation,
            duration=1.0,
            globe=projection == Projection.GLOBE,
        )

    @staticmethod
    def format_population(population: int) -> str:
        if population >= 1_000_000:
            return f"{population / 1_000_000:.1f}M"
        if population >= 1_000:
            return f"{population / 1_000:.0f}K"
        return str(population) if population > 0 else ""

    def destroy(self):
        if self.destroyed:
            return
        self.service.shutdown()
        super().destroy()
