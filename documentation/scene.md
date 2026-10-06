## Scene

The central object of the rendering pipeline is the `Scene`.

It is created in the [SceneBuilder](../src/python/scene_builder.py) and managed by the [SceneController](../src/python/scene_controller.py).

The scene acts as the central rendering container and is responsible for:

* Managing all renderable objects (`drawables`)
* Managing all shaders
* Managing animated objects
* Storing the active camera
* Updating shared rendering data through a Uniform Buffer Object (UBO)
* Executing the render loop

The scene itself is agnostic to any domain specific logic.

### Scene Structure

The scene organizes rendering resources into several collections:

| Collection             | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `shaders`              | Standard 3D rendering shaders.                    |
| `screen_space_shaders` | Post-processing and screen-space shaders.         |
| `drawables`            | Renderable models and objects.                    |
| `animateables`         | Objects that require per-frame animation updates. |
| `camera`               | Active camera used for rendering.                 |
| `ubo`                  | Shared scene data accessible by all shaders.      |

When a shader is added to the scene, it is automatically connected to the shared `SceneUBO`, making camera and lighting information available to all shaders through the `SceneData` uniform block.

### Rendering the Scene

Rendering is performed in three stages:

#### 1. Scene Data Update

Before rendering, the scene updates the `SceneUBO` with the current camera matrices and uploads any modified data to the GPU.

#### 2. 3D Rendering Pass

The multisampled framebuffer is bound and cleared.

All enabled 3D shaders are executed sequentially, rendering their associated drawables.

#### 3. Screen-Space Rendering Pass

After resolving the multisampled framebuffer, screen-space shaders are executed.

These shaders receive the resolved color and depth information and can be used for effects such as:

* Atmosphere rendering
* Post-processing
* Depth-based effects
* Fullscreen overlays

### Animation

Animated objects can be registered in the `animateables` collection.

During each frame, the scene calls:

```python
animate_model(delta_time)
```

for all visible animateable objects.

---

## SceneUBO

The `SceneUBO` stores rendering data that is shared by all shaders.

Using a Uniform Buffer Object avoids repeatedly uploading the same data to each shader individually and ensures that all shaders operate on a consistent view of the scene.

The buffer follows the OpenGL `std140` memory layout and occupies 352 bytes.

### Stored Data

| Field            | Description                                                         |
| ---------------- | ------------------------------------------------------------------- |
| `view`           | Camera view matrix.                                                 |
| `projection`     | Camera projection matrix.                                           |
| `viewProj`       | Combined view-projection matrix.                                    |
| `viewNoTrans`    | View matrix without translation, primarily used for sky rendering.  |
| `invViewProj`    | Inverse view-projection matrix used for world-space reconstruction. |
| `viewPos`        | Current camera position in world space.                             |
| `projectionMode` | Active projection mode identifier.                                  |
| `lightDirection` | Direction of the primary scene light.                               |
| `ambient`        | Ambient light intensity.                                            |

### Camera Data

Whenever the camera changes, the scene automatically updates:

* View matrix
* Projection matrix
* Combined view-projection matrix
* Translation-free view matrix
* Inverse view-projection matrix
* Camera position

Only modified data is uploaded to the GPU, minimizing buffer transfers.

### Lighting Data

The UBO also stores global lighting information.

Currently this includes:

* Primary light direction
* Ambient lighting intensity

All shaders can access these values through the shared `SceneData` uniform block.

### Shader Integration

Any shader registered with the scene automatically binds the `SceneData` uniform block to the scene's UBO binding point.

This provides direct access to camera and lighting data without requiring manual uniform updates.

As a result, new shaders only need to declare the corresponding uniform block and can immediately access all scene-wide rendering information.
