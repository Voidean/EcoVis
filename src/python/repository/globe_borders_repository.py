from typing import Dict

import shapefile
from pyglm import glm

from model.geo_pos import GeoPos
from rendering.data.gl_data_format import Vertex
from rendering.drawables.line import LineCollection
from rendering.geometry.geometry_data import GeometryData, RESTART_INDEX, LINE_VERTEX_FORMAT
from service.geometry_cache import load_geometry
from util.coordinate_constants import GLOBE_RADIUS
from util.coordinate_conversion import geo_pos_to_terrain_elevation, euclidian_distance, globe_heightmap
from util.paths import BORDERS
from util.startup import checkpoint

BORDER_KEYS = ["borders", "contested_borders", "disputed_borders", "pacific_groups"]


def border_data_from_file(shapefile_path, include_tags=None):
    sf = shapefile.Reader(BORDERS / shapefile_path)

    fields = [f[0].lower() for f in sf.fields[1:]]
    feature_idx = fields.index('featurecla') if 'featurecla' in fields else None

    geometry = GeometryData(vertex_format=LINE_VERTEX_FORMAT)
    current_idx = 0

    for shape_index, shape_rec in enumerate(sf.shapeRecords()):
        if shape_index % 25 == 0:
            checkpoint()
        if include_tags is not None and feature_idx is not None:
            tag = str(shape_rec.record[feature_idx]).lower().strip()
            if not any(ext in tag for ext in [t.lower() for t in include_tags]): continue

        shape = shape_rec.shape
        parts = list(shape.parts) + [len(shape.points)]
        for i in range(len(parts) - 1):
            loop = shape.points[parts[i]:parts[i + 1]]
            cumulative_dist = 0.0
            prev_pos = None

            for pt in loop:
                geo_pos = GeoPos.from_degrees(pt[0], pt[1])
                geo_pos.elevation = geo_pos_to_terrain_elevation(geo_pos)
                if prev_pos:
                    cumulative_dist += euclidian_distance(prev_pos, geo_pos)

                geometry.vertices.append(Vertex(position=glm.vec4(*geo_pos, cumulative_dist)))
                geometry.indices.append(current_idx)
                current_idx += 1
                prev_pos = geo_pos

            geometry.indices.append(RESTART_INDEX)

    return geometry


def load_all_borders() -> Dict[str, LineCollection]:
    coast_file = "ne_10m_coastline.shp"
    coast_geometry = load_geometry(
        "coastlines",
        border_data_from_file,
        coast_file,
    )
    coast = LineCollection(coast_geometry, dashed=False)
    checkpoint()

    land_file = "ne_10m_admin_0_boundary_lines_land.shp"
    normal_tags = ["International boundary", "Indefinite"]
    normal_geometry = load_geometry("borders_normal", border_data_from_file, land_file,
                                    include_tags=normal_tags)
    normal_b = LineCollection(normal_geometry, dashed=False)
    checkpoint()

    contested_tags = ["Disputed", "Line of Control", "Unrecognized", "Overlay limit"]
    contested_geometry = load_geometry("borders_contested", border_data_from_file, land_file,
                                       include_tags=contested_tags)
    contested_b = LineCollection(contested_geometry, dashed=True, dash_size=0.0003 * GLOBE_RADIUS,
                                 gap_size=0.0001 * GLOBE_RADIUS)
    checkpoint()

    disputed_file = "ne_10m_admin_0_boundary_lines_disputed_areas.shp"
    disputed_geometry = load_geometry(
        "borders_disputed_extra",
        border_data_from_file,
        disputed_file,
    )
    disputed_extra = LineCollection(disputed_geometry, dashed=True, dash_size=0.0002 * GLOBE_RADIUS,
                                    gap_size=0.0002 * GLOBE_RADIUS)
    checkpoint()

    pacific_file = "ne_10m_admin_0_pacific_groupings.shp"
    pacific_geometry = load_geometry(
        "borders_pacific",
        border_data_from_file,
        pacific_file,
    )
    pacific = LineCollection(pacific_geometry, dashed=True, dash_size=0.0005 * GLOBE_RADIUS,
                             gap_size=0.0003 * GLOBE_RADIUS)
    checkpoint()

    return {
        "coast": coast,
        "borders": normal_b,
        "contested_borders": contested_b,
        "disputed_borders": disputed_extra,
        "pacific_groups": pacific
    }
