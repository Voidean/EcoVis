from collections import defaultdict

from pyglm import glm

from model.power_plant import PowerPlant
from rendering.data.gl_data_format import GlDataAttribute, Vertex, VertexFormat
from rendering.drawables.point_collection import PointCollection
from rendering.geometry.geometry_data import GeometryData


POWER_POINT_VERTEX_FORMAT = VertexFormat(
    GlDataAttribute("geoPos", glm.vec3),
)


class PowerPointRepository:
    """Builds one GPU point collection for each power-plant type."""

    def build_collections(self, plants: list[PowerPlant]) -> dict[str, PointCollection]:
        positions_by_type = defaultdict(list)
        for plant in plants:
            if plant.energietraeger:
                positions_by_type[plant.energietraeger].append(plant.pos.vec3)

        collections = {}
        for plant_type, positions in positions_by_type.items():
            vertices = [Vertex(geoPos=position) for position in positions]
            geometry = GeometryData(
                vertices=vertices,
                indices=range(len(vertices)),
                vertex_format=POWER_POINT_VERTEX_FORMAT,
            )
            collections[plant_type] = PointCollection(geometry)

        return collections
