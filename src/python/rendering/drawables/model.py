from pyglm import glm

from rendering.drawables.drawable import Drawable
from rendering.geometry.mesh import Mesh
from rendering.scene.entity import Entity
from util.culling import cull_frustum


class Model(Drawable):
    def __init__(self, mesh: Mesh):
        super().__init__()
        self.mesh = mesh

    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        self.mesh.use(shader)
        self.mesh.geometry.draw()

    def delete(self):
        self.mesh.delete()


class EntityModel(Model):
    def __init__(self, mesh: Mesh, translation=None, rotation=None, scale=None):
        super().__init__(mesh)
        self.entity = Entity(translation, rotation, scale)

    def animate(self, delta_time):
        self.entity.animate(delta_time)

    def get_bounding_radius(self):
        return (self.mesh.base_radius or 0.0) * max(self.entity.scale.to_list())

    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        if enable_culling and self.mesh.base_radius:
            if cull_frustum(frustum_planes, self.entity.translation, self.get_bounding_radius()): return

        shader.set_bool("useInstancing", False)
        shader.set_mat4("model", glm.mat4(self.entity.get_transform()))

        super().draw(shader, enable_culling, frustum_planes, cull_view_pos)
