from enum import Enum

from util.coordinate_constants import WORLD_UP
from util.geo_projection import *


class Projection(Enum):
    GLOBE = (0, "Globe", project_to_globe, unproject_from_globe)
    EQUIRECTANGULAR = (1, "Equirectangular", project_to_equirectangular, unproject_from_equirectangular)
    MERCATOR = (2, "Mercator", project_to_mercator, unproject_from_mercator)
    ROBINSON = (3, "Robinson", project_to_robinson, unproject_from_robinson)

    def __init__(self, value, display_name, project_fn, unproject_fn):
        self._value_ = value
        self.display_name = display_name
        self.project = project_fn
        self.unproject = unproject_fn

    def up(self, point: glm.vec3) -> glm.vec3:
        return glm.normalize(point) if self == Projection.GLOBE else WORLD_UP
