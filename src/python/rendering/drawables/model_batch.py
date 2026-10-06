from typing import Any

from pyglm import glm

from rendering.data.gl_data_format import ShaderBufferFormat, GlDataAttribute, Instance
from rendering.drawables.drawable import Drawable
from rendering.geometry.mesh import Mesh
from rendering.scene.entity import Entity
from rendering.data.shader_buffer import FormattedShaderBuffer


class ModelBatch(Drawable):
    """Handles instanced rendering of a single model."""

    def __init__(self, mesh: Mesh, instance_format: ShaderBufferFormat, culler=None):
        super().__init__()
        self.mesh = mesh
        self.instance_ssbo = FormattedShaderBuffer(instance_format)
        self.culler = culler
        self.cull_uniforms = {}

    def add_instance(self, instance_data: Instance):
        self.instance_ssbo.append_record(instance_data)

    def upload_instances(self, instances_data: list[Instance]):
        self.instance_ssbo.upload_records(instances_data)

    def update_instance(self, instance_index: int, instance_data: Instance):
        self.instance_ssbo.update_record(instance_index, instance_data)

    def update_instance_field(self, instance_index: int, field_name: str, field_data: Any):
        self.instance_ssbo.update_field(instance_index, field_name, field_data)

    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        if self.instance_ssbo.count == 0: return

        if enable_culling and self.culler is not None:
            self.culler.cull(
                self.instance_ssbo, frustum_planes, cull_view_pos, self.cull_uniforms
            )
            shader.use()
            self.culler.culled_ssbo.bind(0)
            self.mesh.use(shader)
            self.mesh.geometry.draw_indirect(self.culler.command_buffer)
            return

        self.instance_ssbo.bind(0)
        self.mesh.use(shader)
        self.mesh.geometry.draw_instanced(self.instance_ssbo.count)

    def delete(self):
        self.instance_ssbo.delete()
        if self.culler is not None:
            self.culler.delete()
        self.mesh.delete()


ENTITY_FORMAT = ShaderBufferFormat(
    GlDataAttribute("model", glm.mat4)
)


class EntityModelBatch(ModelBatch):
    def __init__(self, mesh: Mesh, instance_format: ShaderBufferFormat = ENTITY_FORMAT, culler=None):
        super().__init__(mesh, instance_format, culler)
        self.entities = list[Entity]()

    def animate(self, delta_time):
        for entity in self.entities: entity.animate(delta_time)
        self.upload_instances()

    def add_instance(self, entity: Entity):
        self.entities.append(entity)
        super().add_instance(entity.to_instance())

    def upload_instances(self, entities: list[Entity] | None = None):
        if entities is not None:
            self.entities = entities
        super().upload_instances([e.to_instance() for e in self.entities])

    def update_instance(self, index, entity: Entity | None = None):
        if entity:
            self.entities[index] = entity
        super().update_instance(index, self.entities[index].to_instance())


SURFACE_ENTITY_FORMAT = ShaderBufferFormat(
    GlDataAttribute("model", glm.mat4),
    GlDataAttribute("geoPos", glm.vec3)
)

class SurfaceEntityModelBatch(EntityModelBatch):
    def __init__(self, mesh: Mesh, culler=None):
        super().__init__(mesh, SURFACE_ENTITY_FORMAT, culler)
