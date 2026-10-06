import numpy as np
from pyglm import glm

from model.state.render_state import render_state
from rendering.scene.camera import Camera
from rendering.scene.entity import Entity
from rendering.textures.frame_buffer_array import FrameBufferArray
from util.coordinate_constants import GLOBE_RADIUS
from util.coordinate_conversion import world_pos_altitude
from util.screen_projection import screen_space_to_world_space_approx

DEFAULT_SHADOW_MAP_RESOLUTION = 2048

DEFAULT_SHADOW_CASCADES = 4
MAX_SHADOW_CASCADES = 10
DEPTH_EXTENSION = 150_000


class DirectionalLight(Entity):
    def __init__(self, light_direction=glm.dvec3(0, -1, 0),
                 shadow_map_resolution=DEFAULT_SHADOW_MAP_RESOLUTION,
                 num_cascades=DEFAULT_SHADOW_CASCADES):
        super().__init__()
        self.light_direction = glm.normalize(light_direction)
        self.shadow_map_resolution = shadow_map_resolution
        self.num_cascades = num_cascades
        self.shadow_distance = GLOBE_RADIUS / 2 # Max distance shadows will be rendered

        self.cascade_view_projections = []
        self.cascade_origins = []
        self.cascade_splits = []
        self.cascade_frustums = []  # For culling
        self.cascade_cull_positions = []  # For occlusion culling

        self.shadow_map_buffer = FrameBufferArray(
            shadow_map_resolution, shadow_map_resolution, num_cascades,
            use_color=False, use_depth=True
        )

    def set_resolution(self, shadow_map_resolution, num_cascades):
        self.shadow_map_resolution = shadow_map_resolution
        self.num_cascades = num_cascades
        self.shadow_map_buffer.update_size(shadow_map_resolution, shadow_map_resolution, num_cascades)

    def update_cascades(self, camera: Camera):
        """
        Slices the main_camera's frustum and generates the orthographic
        view-projection matrices for each cascade.
        """
        self.cascade_view_projections.clear()
        self.cascade_origins.clear()
        self.cascade_splits.clear()
        self.cascade_frustums.clear()
        self.cascade_cull_positions.clear()

        if self.num_cascades == 0:
            return

        inv_camera_view = glm.inverse(camera.view_transform)

        terrain_distance = world_pos_altitude(camera.translation)

        near = max(camera.near, terrain_distance * 0.9)
        far = max(near + camera.near, terrain_distance + self.shadow_distance)

        screen_center = glm.dvec2(camera.width * 0.5, camera.height * 0.5)
        surface_pos = screen_space_to_world_space_approx(
            screen_center, camera, render_state.projection
        )
        view_distance = (
            glm.distance(camera.translation, surface_pos)
            if surface_pos is not None
            else terrain_distance
        )
        distance_ratio = min(max(view_distance / 250_000.0, 0.0), 1.0)
        high_altitude_weight = (
                distance_ratio * distance_ratio * (3.0 - 2.0 * distance_ratio)
        )
        near_detail_weight = 1.0 - high_altitude_weight

        lambda_val = 0.95 + 0.05 * near_detail_weight
        split_exponent = 1.0 + near_detail_weight
        splits = []
        for i in range(1, self.num_cascades + 1):
            p = (i / self.num_cascades) ** split_exponent
            log_split = near * ((far / near) ** p)
            lin_split = near + (far - near) * p
            split_val = lambda_val * log_split + (1.0 - lambda_val) * lin_split
            splits.append(split_val)
            self.cascade_splits.append(split_val)

        # Compute the View-Projection Matrix & Frustum for each cascade
        tan_half_fov = glm.tan(camera.fov / 2.0)

        for i in range(self.num_cascades):
            d_prev = near if i == 0 else splits[i - 1]
            d_curr = splits[i]

            # View space frustum corners
            h_n = tan_half_fov * d_prev
            w_n = h_n * camera.aspect_ratio
            h_f = tan_half_fov * d_curr
            w_f = h_f * camera.aspect_ratio

            z_near = -d_prev
            z_far = -d_curr

            # 8 corners in camera space
            corners = [
                # Near plane corners
                glm.dvec4(-w_n, h_n, z_near, 1.0),
                glm.dvec4(w_n, h_n, z_near, 1.0),
                glm.dvec4(w_n, -h_n, z_near, 1.0),
                glm.dvec4(-w_n, -h_n, z_near, 1.0),
                # Far plane corners
                glm.dvec4(-w_f, h_f, z_far, 1.0),
                glm.dvec4(w_f, h_f, z_far, 1.0),
                glm.dvec4(w_f, -h_f, z_far, 1.0),
                glm.dvec4(-w_f, -h_f, z_far, 1.0)
            ]

            # Transform corners to World Space
            world_corners = [glm.dvec3(inv_camera_view * c) for c in corners]

            # Build standard light view matrix
            up = glm.dvec3(0.0, 1.0, 0.0)
            if glm.abs(glm.dot(self.light_direction, up)) > 0.99:
                up = glm.dvec3(0.0, 0.0, 1.0)  # Avoid collinearity with parallel vectors

            # Use a rotation-only light view. Translation is represented by the
            # per-cascade floating origin below so it can be snapped independently.
            light_view = glm.lookAt(glm.dvec3(0.0), -self.light_direction, up)
            cull_position = self.light_direction * (2.0 * GLOBE_RADIUS)

            # Find the cascade bounds in absolute light space using double precision.
            light_space_corners = [
                glm.dvec3(light_view * glm.dvec4(c, 1.0))
                for c in world_corners
            ]

            min_x = min(c.x for c in light_space_corners)
            max_x = max(c.x for c in light_space_corners)
            min_y = min(c.y for c in light_space_corners)
            max_y = max(c.y for c in light_space_corners)
            min_z = min(c.z for c in light_space_corners)
            max_z = max(c.z for c in light_space_corners)

            # Snap the floating origin itself to the shadow texel grid.
            grid_size = max(max_x - min_x, max_y - min_y, 1e-6)
            usable_resolution = max(self.shadow_map_resolution - 2, 1)
            texel_size = grid_size / usable_resolution

            light_center = glm.dvec3(
                (min_x + max_x) * 0.5,
                (min_y + max_y) * 0.5,
                (min_z + max_z) * 0.5,
            )
            light_center.x = glm.round(light_center.x / texel_size) * texel_size
            light_center.y = glm.round(light_center.y / texel_size) * texel_size

            light_origin = glm.dvec3(glm.inverse(light_view) * glm.dvec4(light_center, 1.0))

            # Keep a one-texel guard band on every side so rounding the center cannot clip a frustum corner.
            half_grid_size = texel_size * self.shadow_map_resolution * 0.5
            min_x = min_y = -half_grid_size
            max_x = max_y = half_grid_size

            relative_light_space_corners = [
                glm.dvec3(light_view * glm.dvec4(c - light_origin, 1.0))
                for c in world_corners
            ]
            min_z = min(c.z for c in relative_light_space_corners)
            max_z = max(c.z for c in relative_light_space_corners)

            # Extend Z range backward/forward to catch shadow-casting geometry outside the frustum
            min_z -= 100.0
            max_z += DEPTH_EXTENSION

            # Reversed-Z orthogonal projection for the light.
            light_proj = glm.dmat4(glm.orthoZO(min_x, max_x, min_y, max_y, -max_z, -min_z))

            # Combine matrices
            light_view_proj = glm.mat4(light_proj * light_view)

            self.cascade_view_projections.append(light_view_proj)
            self.cascade_origins.append(glm.dvec4(light_origin, 0.0))
            self.cascade_frustums.append(self._extract_frustum_planes(light_view_proj, light_origin))
            self.cascade_cull_positions.append(glm.vec3(cull_position))

    def _extract_frustum_planes(self, m: glm.mat4, origin: glm.dvec3):
        """
        Extracts 6 normalized frustum planes into a (6, 4) numpy array
        matching the camera's format for culling.
        """
        # Convert glm mat4 to numpy array (column-major to row-major)
        m_np = np.array(m.to_list(), dtype=np.float64).reshape(4, 4).T

        planes = np.zeros((6, 4), dtype=np.float64)

        planes[0] = m_np[3] + m_np[0]  # Left
        planes[1] = m_np[3] - m_np[0]  # Right
        planes[2] = m_np[3] + m_np[1]  # Bottom
        planes[3] = m_np[3] - m_np[1]  # Top
        planes[4] = m_np[2]  # Near (zero-to-one clip depth)
        planes[5] = m_np[3] - m_np[2]  # Far

        # Normalize each plane's normal (xyz)
        origin_np = np.array([origin.x, origin.y, origin.z], dtype=np.float64)
        for i in range(6):
            n = planes[i][:3]
            length = np.linalg.norm(n)
            if length > 0:
                planes[i] /= length

            # Convert the local plane equation to absolute world coordinates
            # for the existing culling path: n.(world - origin) + d = 0.
            planes[i, 3] -= np.dot(planes[i, :3], origin_np)

        return planes.astype(np.float32)

    def delete(self):
        self.shadow_map_buffer.delete()
