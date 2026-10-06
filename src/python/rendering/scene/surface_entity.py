from pyglm import glm

from model.geo_pos import GeoPos
from rendering.data.gl_data_format import Instance
from rendering.scene.entity import Entity


class SurfaceEntity(Entity):
    def __init__(self, geo_pos: GeoPos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_pos = geo_pos

    def to_instance(self):
        return Instance(model=glm.mat4(self.get_transform()), geoPos=self.geo_pos.vec3)
