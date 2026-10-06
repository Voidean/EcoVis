import logging
import itertools
from dataclasses import fields

import ijson
from pyglm import glm

from model.geo_pos import GeoPos
from model.power_plant import PowerPlant
from rendering.geometry.geometry_data import GeometryData, RESTART_INDEX, LINE_VERTEX_FORMAT
from rendering.data.gl_data_format import Vertex
from repository.power_data.sqlite_power_metadata_repository import SqlitePowerMetadataRepository
from util.coordinate_conversion import geo_pos_to_terrain_elevation, euclidian_distance
from util.paths import OSM
from util.startup import checkpoint

logger = logging.getLogger(__name__)


class GeoJsonSqlitePowerMetadataRepository(SqlitePowerMetadataRepository):
    def init_repository(self):
        super().__init__()

    file_path = OSM / "power_plants.geojson"

    def parse_and_store(self):
        """Loads PowerPlant Metadata from a geojson file and maps their locations in a R-Tree."""
        field_names = [f.name for f in fields(PowerPlant)]
        placeholders = ", ".join(["?"] * len(field_names))
        insert_sql = f"INSERT OR REPLACE INTO powerplants ({', '.join(field_names)}) VALUES ({placeholders})"

        logger.info("Loading power plants from GeoJSON")
        indexed_count = 0
        with self._connect() as cursor:
            try:
                with open(self.file_path, "rb") as f:
                    stream = ijson.items(f, "features.item")
                    stream = itertools.islice(stream, 0, 10000)

                    for feature in stream:
                        plant = PowerPlant.from_geojson_feature(feature)
                        if not plant: continue
                        values = [self._to_db_value(getattr(plant, field)) for field in field_names]
                        cursor.execute(insert_sql, values)

                        self._insert_into_rtree(plant.plant_id, plant.latitude, plant.longitude)
                        indexed_count += 1
                        # store types
                        type = plant.energietraeger
                        if not type in self.plant_types: self.plant_types.append(type)

            except FileNotFoundError:
                logger.warning("File %s not found; loading no power plants", self.file_path)
            logger.info("Loaded %s power plants from GeoJSON", indexed_count)


def load_power_lines(geojson_path, max_elements=None):
    """Loads all LineString Features from a geojson file and aligns them to a heightmap on a globe.
        Params:
            geojson_path: Path to geojson file
            heightmap: Heightmap np.arr
            vertical_scale: Vertical scale factor for heightmap
            max_elements: Max number of elements to load
        Returns:
            A Tuple of np.arrays containing vertex and index data of LineStrings. Different lines are separated by RESTART_INDEX values
    """
    geometry = GeometryData(vertex_format=LINE_VERTEX_FORMAT)
    current_idx = 0

    try:
        with open(OSM / geojson_path, "rb") as f:
            stream = ijson.items(f, "features.item")
            stream = itertools.islice(stream, 0, max_elements)
            for feature_index, feature in enumerate(stream):
                if feature_index % 100 == 0:
                    checkpoint()
                feature_mesh = feature.get("geometry", {})
                if feature_mesh.get("type") != "LineString":
                    continue
                cumulative_dist = 0.0
                prev_pos = None

                for c in feature_mesh.get("coordinates", []):
                    geo_pos = GeoPos.from_degrees(float(c[0]), float(c[1]))
                    geo_pos.elevation = geo_pos_to_terrain_elevation(geo_pos)

                    if prev_pos:
                        distance = euclidian_distance(prev_pos, geo_pos)
                        if distance < 0.0002: continue
                        cumulative_dist += distance

                    geometry.vertices.append(Vertex(position=glm.vec4(*geo_pos, cumulative_dist)))
                    geometry.indices.append(current_idx)
                    current_idx += 1
                    prev_pos = geo_pos

                geometry.indices.append(RESTART_INDEX)
    except FileNotFoundError:
        logger.warning("File %s not found; loading no power lines", geojson_path)

    return geometry
