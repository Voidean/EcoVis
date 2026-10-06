from rendering.geometry.geometry import Geometry
from rendering.geometry.geometry_data import GeometryData
from rendering.textures.texture import Texture


class Mesh:
    def __init__(self, geometry: Geometry | GeometryData, textures=None):
        self.geometry = Geometry.from_data(geometry)

        self.textures = textures if textures else {
            "diffuse": Texture.empty(),
            "normalMap": Texture.empty_normal(),
        }

    @property
    def base_radius(self):
        return self.geometry.base_radius

    def use(self, shader):
        for i, (tex_name, tex) in enumerate(self.textures.items()):
            unit = i + len(shader.textures)
            tex.use(unit)
            shader.set_int(f"material.{tex_name}", unit)

        self.geometry.use()

    def delete(self):
        self.geometry.delete()
        for tex in self.textures.values():
            tex.delete()
