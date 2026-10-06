import numpy as np
from OpenGL.GL import *
from pyglm import glm

from rendering.data.gl_data_format import ShaderBufferFormat
from rendering.data.shader_buffer import ShaderBuffer, FormattedShaderBuffer
from rendering.geometry.mesh import Mesh
from rendering.shaders.compute_shader import ComputeShader


class GpuInstanceCuller:
    """Compacts visible instance records for an indirect model-batch draw."""

    def __init__(self, mesh: Mesh, instance_format: ShaderBufferFormat, cull_shader: ComputeShader):
        self.cull_shader = cull_shader
        self.culled_ssbo = FormattedShaderBuffer(instance_format)
        initial_command = np.array([mesh.geometry.count, 0, 0, 0, 0], dtype=np.uint32)
        self.command_buffer = ShaderBuffer(initial_command, usage=GL_DYNAMIC_DRAW, target=GL_DRAW_INDIRECT_BUFFER)

    def sync_buffer_size(self, instance_ssbo: FormattedShaderBuffer):
        self.culled_ssbo.reserve(instance_ssbo.capacity_bytes)
        self.culled_ssbo.count = instance_ssbo.count

    def cull(self, instance_ssbo: FormattedShaderBuffer, frustum_planes, cull_view_pos,
             shader_uniforms=None):
        self.sync_buffer_size(instance_ssbo)
        # Reset instanceCount to 0 in the command buffer
        self.command_buffer.buffer_sub_data(data=b'\x00\x00\x00\x00', offset=4)

        instance_ssbo.bind(0)
        self.culled_ssbo.bind(1)
        self.command_buffer.bind(2, target=GL_SHADER_STORAGE_BUFFER)

        self.cull_shader.use()
        self.cull_shader.set_int("instanceCount", instance_ssbo.count)
        for name, value in (shader_uniforms or {}).items():
            self.cull_shader.set_uniform(name, value() if callable(value) else value)
        if frustum_planes is None:
            frustum_planes = []
        frustum_planes = np.asarray(frustum_planes, dtype=np.float32).reshape(-1, 4)[:6]
        self.cull_shader.set_int("cullFrustumPlaneCount", len(frustum_planes))
        if len(frustum_planes) > 0:
            self.cull_shader.set_vec4_array("cullFrustumPlanes", frustum_planes)
        if cull_view_pos is None:
            cull_view_pos = glm.vec3(0.0)
        self.cull_shader.set_vec3("cullViewPos", glm.vec3(cull_view_pos))

        group_x = int(np.ceil(instance_ssbo.count / 64.0))
        self.cull_shader.dispatch(group_x, 1, 1)

        # Barrier to ensure compute writes are done before vertex shader reads
        glMemoryBarrier(GL_COMMAND_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT)

    def delete(self):
        self.culled_ssbo.delete()
        self.command_buffer.delete()


# Kept as a compatibility wrapper for existing callers such as the map tiles.
from rendering.drawables.model_batch import ModelBatch


class CulledModelBatch(ModelBatch):
    def __init__(self, mesh: Mesh, instance_format: ShaderBufferFormat, cull_shader: ComputeShader):
        super().__init__(mesh, instance_format, GpuInstanceCuller(mesh, instance_format, cull_shader))
