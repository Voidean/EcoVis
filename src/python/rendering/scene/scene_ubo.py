from pyglm import glm

from rendering.data.gl_data_format import UniformBufferFormat, GlDataAttribute
from rendering.data.uniform_buffer import UniformBuffer
from rendering.scene.camera import Camera
from rendering.scene.directional_light import DirectionalLight, MAX_SHADOW_CASCADES

SCENE_UBO_FORMAT = UniformBufferFormat(
    GlDataAttribute("view",            glm.mat4 ),
    GlDataAttribute("projection",      glm.mat4 ),
    GlDataAttribute("viewProjection",  glm.mat4 ),
    GlDataAttribute("viewNoTrans",     glm.mat4 ),
    GlDataAttribute("viewProjNoTrans", glm.mat4 ),
    GlDataAttribute("invViewProj",     glm.mat4 ),

    GlDataAttribute("dViewPos",        glm.dvec3),
    GlDataAttribute("viewPos",         glm.vec3 ),

    GlDataAttribute("projectionMode",  int      ),
    GlDataAttribute("verticalScale",   float    ),

    GlDataAttribute("enableShadows",   bool     ),
    GlDataAttribute("lightDirection",  glm.vec3 ),
    GlDataAttribute("ambient",         float    ),


    GlDataAttribute("frustumPlanes",   glm.vec4, array_size=5),

    GlDataAttribute("lightSpaceMatrices", glm.mat4, array_size=MAX_SHADOW_CASCADES),
    GlDataAttribute("lightSpaceOrigins", glm.dvec4, array_size=MAX_SHADOW_CASCADES),
    GlDataAttribute("cascadeSplits", float, array_size=MAX_SHADOW_CASCADES),
    GlDataAttribute("cascadeCount", int),
)


class SceneUniformBuffer(UniformBuffer):
    def __init__(self, binding_point=0):
        super().__init__(SCENE_UBO_FORMAT, binding_point)

    def update_view_matrices(self, camera: Camera):
        if camera.changed:
            camera.changed = False

            view = camera.view_transform
            proj = camera.projection_transform
            view_proj = proj * view

            view_no_trans = glm.dmat4(glm.dmat3(view))
            view_proj_no_trans = proj * view_no_trans

            inv_view_proj = glm.inverse(view_proj)

            self.set_field("view",            glm.mat4(view)               )
            self.set_field("projection",      glm.mat4(proj)               )
            self.set_field("viewProjection",  glm.mat4(view_proj)          )
            self.set_field("viewNoTrans",     glm.mat4(view_no_trans)      )
            self.set_field("viewProjNoTrans", glm.mat4(view_proj_no_trans) )
            self.set_field("invViewProj",     glm.mat4(inv_view_proj)      )
            self.set_field("dViewPos",        glm.dvec3(camera.translation))
            self.set_field("viewPos",         glm.vec3(camera.translation) )
            self.set_field("frustumPlanes",   camera.frustum_planes        )

    def update_projection(self, projection: int):
        self.set_field("projectionMode", projection)

    def update_vertical_scale(self, vertical_scale: float):
        self.set_field("verticalScale", vertical_scale)

    def update_light_direction(self, light_dir: glm.vec3):
        self.set_field("lightDirection", glm.vec3(light_dir))

    def update_shadows(self, enable_shadows: bool):
        self.set_field("enableShadows", enable_shadows)

    def update_ambient(self, ambient: float):
        self.set_field("ambient", ambient)

    def update_cascades(self, light_source: DirectionalLight):
        self.set_field("lightSpaceMatrices", light_source.cascade_view_projections)
        self.set_field("lightSpaceOrigins", light_source.cascade_origins)
        self.set_field("cascadeSplits", light_source.cascade_splits)
        self.set_field("cascadeCount", light_source.num_cascades)
