import math

import numpy as np
from pyglm import glm

from rendering.scene.entity import Entity
from util.coordinate_constants import GLOBE_RADIUS
from util.culling import cull_frustum

CAMERA_TO_GL = glm.dmat4(
    -1, 0, 0, 0,
     0, 0, 1, 0,
     0, 1, 0, 0,
     0, 0, 0, 1,
)


def view_matrix(translation: glm.dvec3, rotation: glm.dquat):
    inv_rotation = glm.mat4_cast(glm.inverse(rotation))
    inv_translation = glm.translate(glm.dmat4(1.0), -translation)

    return CAMERA_TO_GL * inv_rotation * inv_translation


def perspective_matrix(fov: float, aspect: float, near: float = 1.0):
    f = 1.0 / math.tan(fov * 0.5)

    return glm.dmat4(
        f / aspect, 0.0, 0.0,  0.0,
               0.0,   f, 0.0,  0.0,
               0.0, 0.0, 0.0, -1.0,
               0.0, 0.0, near, 0.0
    )


class Camera(Entity):
    def __init__(self, translation=None, rotation=None, fov=math.radians(45.0)):
        super().__init__(translation=translation, rotation=rotation)
        self.changed = True

        self.aspect_ratio = None
        self.width, self.height = None, None
        self.pixel_scale_x, self.pixel_scale_y = None, None

        self.fov = fov
        self.near = 1.0

        self.projection_transform = None
        self.view_transform = None
        self.frustum_planes = None

    def initialize(self, viewport_size, content_scale):
        self.set_viewport_size(*viewport_size)
        self.pixel_scale_x, self.pixel_scale_y = content_scale
        self.apply_view_transform()

    def apply_view_transform(self):
        self.view_transform = view_matrix(self.translation, self.rotation)
        self.update_frustum_planes()
        self.changed = True

    def set_viewport_size(self, width, height):
        self.width, self.height = width, height
        self.aspect_ratio = max(width, 1) / max(height, 1)
        self.apply_projection_transform()

    def set_fov(self, fov):
        self.fov = fov
        self.apply_projection_transform()

    def apply_projection_transform(self):
        self.projection_transform = perspective_matrix(self.fov, self.aspect_ratio, near=self.near)
        self.update_frustum_planes()
        self.changed = True

    def update_frustum_planes(self):
        if self.projection_transform is None or self.view_transform is None: return

        # Convert glm mat4 to numpy array (column-major to row-major)
        m = np.array((self.projection_transform * self.view_transform).to_list(), dtype=np.float32).reshape(4, 4).T

        planes = np.zeros((5, 4), dtype=np.float32)

        planes[0] = m[3] + m[0]  # Left
        planes[1] = m[3] - m[0]  # Right
        planes[2] = m[3] + m[1]  # Bottom
        planes[3] = m[3] - m[1]  # Top
        planes[4] = m[3] + m[2]  # Near

        # Normalize each plane
        for i in range(5):
            n = planes[i][:3]
            length = np.linalg.norm(n)
            if length > 0:
                planes[i] /= length

        self.frustum_planes = planes

    def screen_ray(self, screen_pos):
        x, y = screen_pos

        ndc_x = (2.0 * x) / self.width - 1.0
        ndc_y = 1.0 - (2.0 * y) / self.height

        clip = glm.dvec4(ndc_x, ndc_y, -1.0, 1.0)

        inv_proj = glm.inverse(self.projection_transform)

        eye = inv_proj * clip
        eye = glm.dvec4(eye.x, eye.y, -1.0, 0.0)

        inv_view = glm.inverse(self.view_transform)

        world = inv_view * eye

        ray_dir = glm.normalize(glm.dvec3(world))

        return self.translation, ray_dir
