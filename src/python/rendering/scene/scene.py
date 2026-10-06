from OpenGL.GL import *

from rendering.scene.camera import Camera
from rendering.scene.directional_light import DirectionalLight
from rendering.textures.frame_buffer import FrameBuffer
from rendering.scene.scene_ubo import SceneUniformBuffer
from rendering.shaders.shader import Shader


class Scene:
    def __init__(self):
        self.ubo = SceneUniformBuffer(binding_point=0)

        self.shaders = {}  # id -> shader reference
        self.screen_space_shaders = {}  # id -> shader reference
        self.shadow_shaders = {}  # id -> shader reference

        self.drawables = {}  # id -> model reference
        self.animateables = []

        self.enable_shadows = True

        self.camera = Camera()
        self.light_source = DirectionalLight()

    def add_shader(self, shader_id, shader: Shader):
        self.shaders[shader_id] = shader
        shader.bind_ubo("SceneData", self.ubo.binding_point)

    def add_screen_space_shader(self, shader_id, shader: Shader):
        self.screen_space_shaders[shader_id] = shader
        shader.bind_ubo("SceneData", self.ubo.binding_point)

    def add_shadow_shader(self, shader_id, shader: Shader):
        self.shadow_shaders[shader_id] = shader
        shader.bind_ubo("SceneData", self.ubo.binding_point)

        self.shaders[shader_id].textures["shadowMapArray"] = self.light_source.shadow_map_buffer.depth_tex

    def add_drawable(self, drawable_id, drawable, shader_id):
        self.drawables[drawable_id] = drawable
        self.shaders[shader_id].drawables.append(drawable)
        if shader_id in self.shadow_shaders.keys():
            self.shadow_shaders[shader_id].drawables.append(drawable)

    def animate_all(self, delta_time):
        for a in self.animateables:
            if not a.hidden:
                a.animate(delta_time)

    def render(self, frame_buffer: FrameBuffer):
        # --- Update UBO ---
        self.light_source.update_cascades(self.camera)
        self.ubo.update_cascades(self.light_source)
        self.ubo.update_view_matrices(self.camera)
        self.ubo.upload()

        # --- Shadow Pass ---
        if self.light_source.num_cascades > 0 and self.enable_shadows:
            glDepthMask(GL_TRUE)
            glEnable(GL_DEPTH_TEST)
            glClearDepth(1.0)
            glDepthFunc(GL_LESS)

            glEnable(GL_POLYGON_OFFSET_FILL)
            glPolygonOffset(4.0, 8.0)

            for i in range(self.light_source.num_cascades):
                self.light_source.shadow_map_buffer.bind_layer(i)
                glClear(GL_DEPTH_BUFFER_BIT)

                for shader in self.shadow_shaders.values():
                    shader.use()
                    shader.set_mat4("lightViewProj", self.light_source.cascade_view_projections[i])
                    shader.set_dvec3("lightOrigin", self.light_source.cascade_origins[i].xyz)
                    shader.draw_all(
                        self.light_source.cascade_frustums[i],
                        self.light_source.cascade_cull_positions[i],
                    )

            glDisable(GL_POLYGON_OFFSET_FILL)

        # --- Render 3D ---
        glDepthMask(GL_TRUE)
        glEnable(GL_DEPTH_TEST)
        glClearDepth(0.0)
        glDepthFunc(GL_GREATER)

        frame_buffer.bind()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        for shader in self.shaders.values():
            if shader.disabled: continue
            shader.use()
            shader.draw_all(self.camera.frustum_planes, self.camera.translation)

        # --- Resolve MSAA ---
        glDepthMask(GL_TRUE)
        frame_buffer.resolve()
        frame_buffer.copy_to_screen()

        # --- Render single-sample screen-space passes ---
        for shader in self.screen_space_shaders.values():
            if shader.disabled: continue
            shader.use()
            shader.textures["depthMap"] = frame_buffer.depth_tex
            if frame_buffer.samples > 1:
                shader.textures["depthMapMS"] = frame_buffer.msaa_depth_tex
            elif "depthMapMS" not in shader.textures:
                # Keep the inactive multisample sampler on its own unit. GLSL
                # forbids samplers of different types from aliasing a unit.
                shader.set_int("depthMapMS", len(shader.textures))
            shader.set_int("depthSamples", frame_buffer.samples)
            shader.draw_fullscreen()

    def delete(self):
        for shader in self.shaders.values(): shader.delete()
        for shader in self.screen_space_shaders.values(): shader.delete()
        for shader in self.shadow_shaders.values(): shader.delete()
        for drawable in self.drawables.values(): drawable.delete()
        self.light_source.delete()
        self.ubo.delete()
