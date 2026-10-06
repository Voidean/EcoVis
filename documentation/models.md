# Models

The rendering system supports two types of renderable objects:

* `Model` – renders a single mesh instance.
* `ModelBatch` – renders many instances of the same mesh using GPU instancing.

Both types can be added to the scene and rendered by any compatible shader.

---

## Model

The `Model` class represents a single renderable object.

It combines:

* A mesh
* A transform (`Entity`)
* Visibility state

Example:

```python
earth = Model(
    mesh=earth_mesh,
    translation=glm.vec3(0, 0, 0),
    scale=glm.vec3(1, 1, 1)
)
```

Internally, each model owns an `Entity` object that stores:

* Translation
* Rotation
* Scale

These values are combined into a model matrix before rendering.

---

### Frustum Culling

Before rendering, a model can be tested against the camera frustum.

```python
camera.cull_frustum(
    position,
    radius
)
```

The bounding sphere radius is calculated from:

```python
mesh.base_radius
```

scaled by the largest component of the model scale.

Objects outside the camera view can therefore be skipped automatically, reducing the number of draw calls.

---

### Rendering a Model

Rendering a model performs the following steps:

1. Optional frustum culling
2. Upload the model matrix
3. Bind mesh textures
4. Bind the mesh VAO
5. Execute a draw call

The shader receives:

```glsl
uniform mat4 model;
uniform bool useInstancing;
```

with:

```glsl
useInstancing = false;
```

for regular models.

The mesh is then rendered using:

```cpp
glDrawElements(...)
```

---

## ModelBatch

The `ModelBatch` class renders many copies of the same mesh using OpenGL instancing.

Instead of issuing one draw call per object, all instances are rendered in a single draw call.

This can dramatically improve performance when rendering large numbers of identical objects.

---

### Instance Data

A batch contains:

```python
batch.entities
```

which stores a list of `Entity` objects.

Each entity has its own:

* Position
* Rotation
* Scale

while sharing:

* Mesh
* Material textures
* Shader

This minimizes memory usage and draw call overhead.

---

### GPU Storage

Instance transforms are uploaded to a Shader Storage Buffer Object (SSBO).

Each instance stores a complete model matrix:

```text
mat4 modelMatrix
```

The matrices are uploaded into a contiguous GPU buffer.

The SSBO is bound to:

```cpp
binding = 0
```

and can be accessed directly from shaders.

---

### Adding Instances

New instances can be added dynamically:

```python
batch.add_instance(
    Entity(
        translation=glm.vec3(10, 0, 0)
    )
)
```

The transform is automatically uploaded to the GPU.

If the current GPU buffer is too small, the entire instance buffer is rebuilt automatically.

---

### Updating Instances

Individual transforms can be updated without rebuilding the entire buffer.

```python
batch.entities[index].translation.x += 1
batch.update_instance(index)
```

Only the modified model matrix is transferred to the GPU.

This is significantly more efficient than rebuilding the complete instance buffer every frame.

---

### Rendering a Batch

Before rendering:

```glsl
useInstancing = true;
```

is passed to the shader.

The mesh is then rendered using:

```cpp
glDrawElementsInstanced(...)
```

which renders all instances in a single draw call.

The number of rendered objects is determined by:

```python
len(batch.entities)
```

---

## Shader Support

Shaders that support both regular and instanced rendering typically contain:

```glsl
uniform bool useInstancing;
```

and read model matrices differently depending on the rendering mode.

Example:

```glsl
if(useInstancing) {
    // Load model matrix from SSBO
}
else {
    // Use regular model uniform
}
```

This allows a single shader implementation to support both rendering paths.

---

## Resource Management

Both `Model` and `ModelBatch` own the mesh they render.

Resources should therefore be released when the object is no longer needed:

```python
model.delete()
```

or

```python
batch.delete()
```

This frees:

* Vertex Array Objects (VAOs)
* Vertex Buffers (VBOs)
* Element Buffers (EBOs)
* Instance SSBOs (for batches)

and releases the associated GPU resources.
