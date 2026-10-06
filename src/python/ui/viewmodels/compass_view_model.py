from model.state.render_state import render_state
from rendering.scene.camera import Camera
from ui.view_model import ViewModel
from util.compass_util import (
    get_camera_heading,
    get_camera_surface_foreshortening,
    snap_camera_to_north,
)


class CompassViewModel(ViewModel):
    def __init__(self):
        super().__init__()
        self.camera: Camera | None = None
        self.heading = 0.0
        self.surface_scale = 1.0

    @property
    def underside(self) -> bool:
        return self.surface_scale < 0.0

    def set_camera(self, camera: Camera):
        self.camera = camera

    def tick(self):
        if self.camera is None:
            return
        projection = render_state.projection
        self.heading = get_camera_heading(self.camera, projection)
        self.surface_scale = get_camera_surface_foreshortening(
            self.camera,
            projection,
        )

    def snap_to_north(self):
        if self.camera is not None:
            snap_camera_to_north(self.camera, render_state.projection)
