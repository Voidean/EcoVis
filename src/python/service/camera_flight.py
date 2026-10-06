import math
from dataclasses import dataclass

from pyglm import glm

from rendering.scene.camera import Camera
from util.coordinate_constants import GLOBE_RADIUS


@dataclass
class FlightState:
    start_translation: glm.dvec3
    target_translation: glm.dvec3
    start_rotation: glm.dquat
    target_rotation: glm.dquat
    duration: float
    globe: bool
    elapsed: float = 0.0


class CameraFlight:
    def __init__(self, camera: Camera):
        self.camera = camera
        self._state: FlightState | None = None

    def start(
            self,
            target_translation: glm.dvec3,
            target_rotation: glm.dquat,
            duration: float = 1.0,
            globe: bool = False,
    ):
        self._state = FlightState(
            start_translation=glm.dvec3(self.camera.translation),
            target_translation=glm.dvec3(target_translation),
            start_rotation=glm.dquat(self.camera.rotation),
            target_rotation=glm.dquat(target_rotation),
            duration=max(duration, 1e-3),
            globe=globe,
        )

    def update(self, delta_time: float) -> bool:
        if self._state is None:
            return False

        state = self._state
        state.elapsed = min(state.elapsed + delta_time, state.duration)
        progress = state.elapsed / state.duration
        eased = progress * progress * (3.0 - 2.0 * progress)

        if state.globe:
            start_radius = glm.length(state.start_translation)
            target_radius = glm.length(state.target_translation)
            start_direction = state.start_translation / start_radius
            target_direction = state.target_translation / target_radius
            direction, angle = self._slerp_direction(start_direction, target_direction, eased)

            radius = start_radius * (1.0 - eased) + target_radius * eased
            arc_height = min(GLOBE_RADIUS * 0.6, angle * GLOBE_RADIUS * 0.18)
            self.camera.translation = direction * (
                radius + arc_height * math.sin(math.pi * eased)
            )
        else:
            self.camera.translation = (
                state.start_translation * (1.0 - eased)
                + state.target_translation * eased
            )
            horizontal_distance = glm.length(
                glm.dvec2(
                    state.target_translation.x - state.start_translation.x,
                    state.target_translation.y - state.start_translation.y,
                )
            )
            arc_height = min(GLOBE_RADIUS * 0.6, horizontal_distance * 0.18)
            self.camera.translation.z += arc_height * math.sin(math.pi * eased)

        self.camera.rotation = glm.normalize(
            glm.slerp(state.start_rotation, state.target_rotation, eased)
        )

        if progress >= 1.0:
            self.camera.translation = glm.dvec3(state.target_translation)
            self.camera.rotation = glm.dquat(state.target_rotation)
            self._state = None

        self.camera.apply_view_transform()
        return True

    @staticmethod
    def _slerp_direction(start: glm.dvec3, target: glm.dvec3, progress: float):
        dot = glm.clamp(glm.dot(start, target), -1.0, 1.0)
        angle = math.acos(dot)
        if angle < 1e-6:
            return glm.normalize(start * (1.0 - progress) + target * progress), angle

        axis = glm.cross(start, target)
        if glm.length2(axis) < 1e-12:
            fallback = (
                glm.dvec3(0.0, 0.0, 1.0)
                if abs(start.z) < 0.9
                else glm.dvec3(0.0, 1.0, 0.0)
            )
            axis = glm.cross(start, fallback)
        axis = glm.normalize(axis)
        return glm.angleAxis(angle * progress, axis) * start, angle
