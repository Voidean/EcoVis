from math import sin, cos, sqrt, atan2, pi, atan, sinh

from PIL import Image
from pyglm import glm

from model.geo_pos import GeoPos
from rendering.textures.texture import load_image_data
from util.coordinate_constants import GLOBE_RADIUS, MIN_ELEVATION, MAX_ELEVATION
from util.data_texture_util import bilinear_sample, unscale
from util.geo_projection import unproject_from_globe, project_to_globe
from util.paths import TEXTURES

heightmap_image = Image.open(TEXTURES / "globe" / "heightmap.png").convert("L")
globe_heightmap = load_image_data(heightmap_image)


def cube_to_sphere(point: glm.dvec3) -> glm.dvec3:
    # Ensure coordinates are strictly within [-1, 1] to prevent precision drift
    x, y, z = max(-1.0, min(1.0, point.x)), max(-1.0, min(1.0, point.y)), max(-1.0, min(1.0, point.z))

    xsq, ysq, zsq = x ** 2, y ** 2, z ** 2

    return glm.dvec3(
        point.x * sqrt(1 - (ysq + zsq) / 2 + (ysq * zsq) / 3),
        point.y * sqrt(1 - (zsq + xsq) / 2 + (zsq * xsq) / 3),
        point.z * sqrt(1 - (xsq + ysq) / 2 + (xsq * ysq) / 3),
    )


def sphere_to_uv(point: glm.dvec3):
    return geo_pos_to_uv(unproject_from_globe(point))


def world_pos_altitude(world_pos: glm.vec3):
    from model.state.render_state import render_state

    geo_pos = render_state.projection.unproject(world_pos)

    terrain_elevation = geo_pos_to_terrain_elevation(geo_pos)
    return (geo_pos.elevation - terrain_elevation) * render_state.vertical_scale


def geo_pos_to_terrain_elevation(geo_pos: GeoPos, heightmap=globe_heightmap):
    return uv_to_terrain_elevation(geo_pos_to_uv(geo_pos), heightmap)


def uv_to_terrain_elevation(uv, heightmap=globe_heightmap):
    return unscale(bilinear_sample(heightmap, uv), MIN_ELEVATION, MAX_ELEVATION)


def geo_pos_to_uv(geo_pos: GeoPos) -> glm.dvec2:
    u = (geo_pos.lon / pi + 1) / 2
    v = geo_pos.lat / pi + 0.5
    return glm.dvec2(u, v)


def euclidian_distance(geo_pos1: GeoPos, geo_pos2: GeoPos) -> float:
    return glm.distance(project_to_globe(geo_pos1), project_to_globe(geo_pos2))


def haversine_distance(geo_pos1: GeoPos, geo_pos2: GeoPos) -> float:
    d_lon = geo_pos1.lon - geo_pos2.lon
    d_lat = geo_pos1.lat - geo_pos2.lat
    a = sin(d_lat / 2) ** 2 + cos(geo_pos1.lat) * cos(geo_pos2.lat) * sin(d_lon / 2) ** 2
    return 2 * GLOBE_RADIUS * atan2(sqrt(a), sqrt(1 - a))


def quad_tree_node_to_geo_pos(node_pos, uv=glm.dvec2(0.5)) -> GeoPos:
    column, row, level = node_pos
    u, v = uv

    v = 1.0 - v

    n = 2 ** level

    x, y = (column + u) / n, (row + v) / n

    longitude = ((x * 2) - 1) * pi
    latitude = atan(sinh((1 - (y * 2)) * pi))

    return GeoPos(longitude, latitude)
