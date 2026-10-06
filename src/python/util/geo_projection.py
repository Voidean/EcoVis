import math
from math import tan, log, cos, sin, pi, asin, ceil, floor, exp, radians, atan, atan2

from pyglm import glm

from model.geo_pos import GeoPos
from util.coordinate_constants import GLOBE_RADIUS

# Robinson table values
R_X = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427, 0.9216,
       0.8962, 0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
R_Y = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340, 0.4958,
       0.5571, 0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000]


def project_to_globe(geo_pos: GeoPos) -> glm.dvec3:
    from model.state.render_state import render_state

    lon, lat, elev = geo_pos

    x = cos(lat) * sin(lon)
    y = -cos(lat) * cos(lon)
    z = sin(lat)
    r = GLOBE_RADIUS + elev * render_state.vertical_scale

    return glm.dvec3(x, y, z) * r


def project_to_equirectangular(geo_pos: GeoPos) -> glm.dvec3:
    from model.state.render_state import render_state

    lon, lat, elev = geo_pos

    x = lon * GLOBE_RADIUS
    y = lat * GLOBE_RADIUS
    z = elev * render_state.vertical_scale

    return glm.dvec3(x, y, z)


def project_to_mercator(geo_pos: GeoPos) -> glm.dvec3:
    from model.state.render_state import render_state

    lon, lat, elev = geo_pos

    lat = max(-1.4844, min(1.4844, lat))

    x = lon * GLOBE_RADIUS
    y = log(tan(pi / 4.0 + lat / 2.0))
    y = max(-3.0, min(3.0, y)) / 3.0 * pi * GLOBE_RADIUS
    z = elev * render_state.vertical_scale

    return glm.dvec3(x, y, z)


def project_to_robinson(geo_pos: GeoPos) -> glm.dvec3:
    from model.state.render_state import render_state

    lon, lat, elev = geo_pos

    abs_lat_deg = abs(lat) * 180.0 / pi

    f_index = max(0.0, min(18.0, abs_lat_deg / 5.0))

    i = int(floor(f_index))
    j = int(ceil(f_index))

    t = f_index - i

    x_factor = R_X[i] + (R_X[j] - R_X[i]) * t
    y_factor = R_Y[i] + (R_Y[j] - R_Y[i]) * t

    y_sign = 1.0 if lat >= 0.0 else -1.0

    x = lon * x_factor * GLOBE_RADIUS
    y = y_sign * 0.5 * y_factor * pi * GLOBE_RADIUS
    z = elev * render_state.vertical_scale

    return glm.dvec3(x, y, z)


def unproject_from_globe(world_pos: glm.dvec3) -> GeoPos:
    from model.state.render_state import render_state

    r = glm.length(world_pos)
    p = glm.normalize(world_pos)

    lon = atan2(p.x, -p.y)
    lat = asin(p.z)
    elev = (r - GLOBE_RADIUS) / render_state.vertical_scale

    return GeoPos(lon, lat, elev)


def unproject_from_equirectangular(world_pos: glm.dvec3) -> GeoPos:
    from model.state.render_state import render_state

    lon = world_pos.x / GLOBE_RADIUS
    lat = world_pos.y / GLOBE_RADIUS
    elev = world_pos.z / render_state.vertical_scale
    return GeoPos(lon, lat, elev)


def unproject_from_mercator(world_pos: glm.dvec3) -> GeoPos:
    from model.state.render_state import render_state

    lon = world_pos.x / GLOBE_RADIUS

    my = world_pos.y / (GLOBE_RADIUS * pi)
    lat = 2.0 * (atan(exp(my * 3.0)) - (pi / 4.0))

    elev = world_pos.z / render_state.vertical_scale

    return GeoPos(lon, lat, elev)


def unproject_from_robinson(world_pos: glm.dvec3) -> GeoPos:
    from model.state.render_state import render_state

    mx = world_pos.x / (GLOBE_RADIUS * pi)
    my = world_pos.y / (GLOBE_RADIUS * pi)

    y_factor = abs(my) / 0.5
    y_sign = 1.0 if my >= 0 else -1.0

    idx = 0
    for i in range(len(R_Y) - 1):
        if R_Y[i] <= y_factor <= R_Y[i + 1]:
            idx = i
            break

    t = (y_factor - R_Y[idx]) / (R_Y[idx + 1] - R_Y[idx])

    x_factor = R_X[idx] + (R_X[idx + 1] - R_X[idx]) * t
    lon = (mx * pi) / x_factor

    f_index = idx + t
    lat_deg = f_index * 5.0
    lat = radians(lat_deg) * y_sign

    elev = world_pos.z / render_state.vertical_scale

    return GeoPos(lon, lat, elev)


def calculate_geo_pos_from_click(world_pos: glm.vec3, projection):
    geo_pos: GeoPos = projection.unproject(world_pos)
    if geo_pos.elevation > 10_000.0: return None

    if geo_pos.lon < -math.pi or geo_pos.lon > math.pi: return None
    if geo_pos.lat < -math.pi / 2 or geo_pos.lat > math.pi / 2: return None
    return geo_pos
