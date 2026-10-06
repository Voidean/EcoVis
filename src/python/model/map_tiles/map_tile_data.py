from dataclasses import dataclass

from pyglm import glm

from model.geo_pos import GeoPos
from model.projection import Projection
from util.coordinate_conversion import quad_tree_node_to_geo_pos


@dataclass
class MapTileData:
    projection: Projection = None

    size: float = 0.0
    radius: float = 0.0
    center: glm.dvec3 = None

    p_bl: glm.dvec3 = None
    p_br: glm.dvec3 = None
    p_tl: glm.dvec3 = None
    p_tr: glm.dvec3 = None

    min_x: float = None
    max_x: float = None
    min_y: float = None
    max_y: float = None
    min_z: float = None
    max_z: float = None

    def update(self, node, projection):
        if self.projection == projection: return

        lon_min, lat_min = quad_tree_node_to_geo_pos(node.position, glm.dvec2(0.0, 0.0)).coords
        lon_max, lat_max = quad_tree_node_to_geo_pos(node.position, glm.dvec2(1.0, 1.0)).coords
        lon_mid, lat_mid = quad_tree_node_to_geo_pos(node.position, glm.dvec2(0.5, 0.5)).coords

        self.level = node.level

        self.p_bl = projection.project(GeoPos(lon_min, lat_min))
        self.p_br = projection.project(GeoPos(lon_max, lat_min))
        self.p_tl = projection.project(GeoPos(lon_min, lat_max))
        self.p_tr = projection.project(GeoPos(lon_max, lat_max))
        self.center = projection.project(GeoPos(lon_mid, lat_mid))

        self.min_x = min(self.p_bl.x, self.p_br.x, self.p_tl.x, self.p_tr.x)
        self.max_x = max(self.p_bl.x, self.p_br.x, self.p_tl.x, self.p_tr.x)

        self.min_y = min(self.p_bl.y, self.p_br.y, self.p_tl.y, self.p_tr.y)
        self.max_y = max(self.p_bl.y, self.p_br.y, self.p_tl.y, self.p_tr.y)

        self.min_z = min(self.p_bl.z, self.p_br.z, self.p_tl.z, self.p_tr.z)
        self.max_z = max(self.p_bl.z, self.p_br.z, self.p_tl.z, self.p_tr.z)

        self.radius = max(
            glm.distance(self.center, self.p_bl),
            glm.distance(self.center, self.p_br),
            glm.distance(self.center, self.p_tl),
            glm.distance(self.center, self.p_tr),
        )

        self.size = max(
            glm.distance(self.p_bl, self.p_br),
            glm.distance(self.p_tl, self.p_tr),
            glm.distance(self.p_bl, self.p_tl),
            glm.distance(self.p_br, self.p_tr),
        )

        if node.level == 0: self.size *= 3.0  # artificially move lod-0 a bit further away

        self.projection = projection

    def get_distance_sq(self, point: glm.dvec3) -> float:
        def distance_squared(a, b):
            d = a - b
            return glm.dot(d, d)

        closest_p = glm.dvec3(
            glm.clamp(point.x, self.min_x, self.max_x),
            glm.clamp(point.y, self.min_y, self.max_y),
            glm.clamp(point.z, self.min_z, self.max_z)
        )

        center_dist_sq = distance_squared(point, closest_p)
        if center_dist_sq <= 1e-12:
            return 0.0

        to_camera = glm.normalize(point - closest_p)

        incidence = max(glm.dot(to_camera, self.projection.up(closest_p)), 0.1)

        bias_factor = 1.0 / incidence
        bias_factor_sq = bias_factor ** 2

        if self.level < 3:
            return min(
                distance_squared(point, self.p_bl),
                distance_squared(point, self.p_br),
                distance_squared(point, self.p_tl),
                distance_squared(point, self.p_tr),
                center_dist_sq
            ) * 2.0
        else:
            return center_dist_sq * bias_factor_sq
