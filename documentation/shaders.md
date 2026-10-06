# Shaders

The rendering system is built around OpenGL shaders that are loaded from the `resources/shaders` directory.

Supported shader types:

| Type            | Folder                       | Extension |
| --------------- | ---------------------------- | --------- |
| Vertex Shader   | `resources/shaders/vertex`   | `.vert`   |
| Fragment Shader | `resources/shaders/fragment` | `.frag`   |
| Compute Shader  | `resources/shaders/compute`  | `.comp`   |

Shader source files are loaded as plain text, preprocessed, compiled, and linked into OpenGL programs at runtime.

---

## Shader Includes

To avoid duplicating commonly used functions, constants, and variable definitions across multiple shaders, the project implements a lightweight include system similar to the C preprocessor.

Shared code is typically placed in:

```text
resources/shaders/common/
```

Header files can then be included using:

```glsl
#include "common/header_name"
```

For example:

```glsl
#include "common/math"
#include "common/projections"
```

Before compilation, a custom preprocessor resolves all include statements and replaces them with the contents of the referenced `.glsl` files.

The preprocessor also prevents duplicate includes, allowing shared headers to safely include other headers without generating duplicate definitions.

As a result, the final shader source sent to OpenGL is a fully expanded source file containing all required code.

---

## Standard Rendering Shaders

Most rendering is performed using the `Shader` class.

A shader consists of a vertex shader and a fragment shader:

```python
shader = Shader("Globe", "Globe")
```

which loads:

```text
resources/shaders/vertex/Globe.vert
resources/shaders/fragment/Globe.frag
```

The resulting OpenGL program can then be assigned drawables and textures and participate in the scene render loop.

---

## Shader Settings

The `Shader` class exposes several rendering options that control OpenGL state before rendering.

### double_sided

```python
Shader(
    "shader",
    "shader",
    double_sided=True
)
```

Controls face culling.

| Value   | Behavior                                                             |
| ------- | -------------------------------------------------------------------- |
| `False` | Back-face culling enabled. Only front-facing triangles are rendered. |
| `True`  | Face culling disabled. Both sides of a triangle are rendered.        |


---

### additive_blend

```python
Shader(
    "shader",
    "shader",
    additive_blend=True
)
```

Controls blending mode.

| Value   | Behavior                 |
| ------- | ------------------------ |
| `False` | Standard alpha blending. |
| `True`  | Additive blending.       |

Standard alpha blending:

```text
result = source * alpha + destination * (1 - alpha)
```

Additive blending:

```text
result = source + destination
```


---

### custom_blend

```python
Shader(
    "shader",
    "shader",
    custom_blend=True
)
```

Disables automatic blend configuration.

When enabled, the shader is responsible for configuring OpenGL blend state manually.

This is useful for specialized rendering passes that require custom blend equations.

---

### write_depth_buffer

```python
Shader(
    "shader",
    "shader",
    write_depth_buffer=False
)
```

Controls depth buffer writes.

| Value   | Behavior                                 |
| ------- | ---------------------------------------- |
| `True`  | Shader writes depth values.              |
| `False` | Shader does not modify the depth buffer. |

When disabled:

```python
glDepthFunc(GL_LEQUAL)
glDepthMask(GL_FALSE)
```

When enabled:

```python
glDepthFunc(GL_LESS)
glDepthMask(GL_TRUE)
```

which is the normal configuration for opaque geometry.

---

### frustum_culling

```python
Shader(
    "shader",
    "shader",
    frustum_culling=False
)
```

Controls whether drawables are tested against the camera frustum before rendering.

| Value   | Behavior                                      |
| ------- | --------------------------------------------- |
| `True`  | Objects outside the view frustum are skipped. |
| `False` | All assigned drawables are rendered.          |

---

## Textures

Textures can be attached to shaders through the `textures` dictionary.

During rendering, textures are automatically bound to consecutive texture units and corresponding sampler uniforms are updated.

Example:

```python
shader.textures["temperatureMap"] = texture
```

Inside the shader:

```glsl
uniform sampler2D temperatureMap;
```

The texture will automatically be assigned to an available texture unit.

---

## Scene Integration

When a shader is added to the scene:

```python
scene.add_shader("globe", shader)
```

the scene automatically binds the shared `SceneUBO` to the shader.

This allows all shaders to access camera and lighting information through the shared uniform block:

```glsl
layout(std140) uniform SceneData
{
    ...
};
```

which can be imported using `#include "common/SceneDataBuffer"`

---

## Screen-Space Shaders

Screen-space shaders are rendered after the main 3D scene has finished rendering.

Unlike standard shaders, they do not render scene geometry.

Instead, they render a fullscreen quad covering the entire viewport.

Example usage:

```python
scene.add_screen_space_shader(
    "atmosphere",
    atmosphere_shader
)
```

Typical applications include:

* Atmospheric scattering
* Post-processing
* Depth-based effects
* Fullscreen overlays

During rendering, the depth texture from the main framebuffer is automatically provided through:

```glsl
uniform sampler2D depthMap;
```

allowing screen-space shaders to reconstruct scene depth information.

---

## Compute Shaders

Compute shaders provide GPU-based general-purpose computation.

Unlike rendering shaders, they do not produce visible geometry directly.

Example:

```python
compute = ComputeShader("WindParticle")
```

which loads:

```text
resources/shaders/compute/WindParticle.comp
```

Tasks are executed using:

```python
compute.dispatch(x, y, z)
```

where the work group counts correspond to the compute shader's layout definition.

After execution, a memory barrier is automatically inserted:

```python
glMemoryBarrier(
    GL_SHADER_STORAGE_BARRIER_BIT |
    GL_VERTEX_ATTRIB_ARRAY_BARRIER_BIT
)
```

This ensures that all GPU writes are visible before subsequent rendering stages attempt to read the generated data.

Compute shaders can be used for:

* Particle simulation
* Data processing
* GPU-side buffer generation
* Large parallel calculations

---

## Error Reporting

Compilation and linking errors are printed to the console.

Shader compilation errors include:

```text
ERROR::SHADER_COMPILATION_ERROR
```

Program linking errors include:

```text
ERROR::PROGRAM_LINKING_ERROR
```

This allows syntax errors, missing uniforms, incompatible interfaces, and other OpenGL shader issues to be diagnosed during application startup.
