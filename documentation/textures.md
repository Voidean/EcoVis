## Textures

The `Texture` class is the central abstraction for GPU textures within the rendering system.

It provides:

* Texture creation from NumPy arrays
* Texture loading from image files
* Automatic OpenGL format selection
* Dynamic texture updates
* Persistent GPU upload buffers
* Automatic mipmap generation
* Optional CPU-side memory retention

The class is designed to efficiently handle both static assets (e.g. Earth textures, normal maps, gradients) and dynamic datasets (e.g. weather textures updated every time step).

---

## Supported Data Types

Textures can be created directly from NumPy arrays.

Supported array types:

| NumPy Type   | OpenGL Format       |
| ------------ | ------------------- |
| `np.uint8`   | `GL_UNSIGNED_BYTE`  |
| `np.uint16`  | `GL_UNSIGNED_SHORT` |
| `np.float16` | `GL_HALF_FLOAT`     |
| `np.float32` | `GL_FLOAT`          |

The texture format is automatically derived from the array data type and channel count.

---

## Supported Channel Counts

The texture class supports between one and four channels.

| Channels | Format    |
| -------- | --------- |
| 1        | Red       |
| 2        | Red-Green |
| 3        | RGB       |
| 4        | RGBA      |

Examples:

```python
rgba_texture = Texture(image_data)
```

---

## Creating Textures from Arrays

Textures can be created directly from NumPy data.

Example:

```python
data = np.random.rand(512, 1024).astype(np.float32)

texture = Texture(data)
```

Two-dimensional arrays are automatically interpreted as single-channel textures.

Internally:

```python
height, width
```

becomes:

```python
height, width, 1
```

allowing weather datasets to be used directly as textures.

---

## Loading Images

Images can be loaded from the texture resource directory.

Example:

```python
texture = Texture.from_file("globe/diffuse.jpg")
```

The file path is resolved relative to:

```text
resources/textures/
```

Images are automatically converted into a NumPy array and uploaded to the GPU.

Supported image formats depend on Pillow and include:

* PNG
* JPG / JPEG
* BMP
* TIFF
* WebP

---

## Texture Parameters

Several common OpenGL texture parameters can be configured during construction.

### repeat_s

Controls horizontal texture wrapping.

```python
Texture(
    data,
    repeat_s=True
)
```

| Value   | Behavior                                   |
| ------- | ------------------------------------------ |
| `True`  | Repeat texture horizontally (`GL_REPEAT`). |
| `False` | Clamp horizontally (`GL_CLAMP_TO_EDGE`).   |

---

### repeat_t

Controls vertical texture wrapping.

```python
Texture(
    data,
    repeat_t=True
)
```

| Value   | Behavior                                 |
| ------- | ---------------------------------------- |
| `True`  | Repeat texture vertically (`GL_REPEAT`). |
| `False` | Clamp vertically (`GL_CLAMP_TO_EDGE`).   |

---

### mipmaps

Controls automatic mipmap generation.

```python
Texture(
    data,
    mipmaps=True
)
```

| Value   | Behavior                                      |
| ------- | --------------------------------------------- |
| `True`  | Generate mipmaps and use trilinear filtering. |
| `False` | Use only the base texture level.              |

Mipmaps improve rendering quality when textures are viewed at a distance and reduce aliasing artifacts.

---

### keep_in_memory

Controls whether the original NumPy array remains in CPU memory after upload.

```python
Texture(
    data,
    keep_in_memory=True
)
```

| Value   | Behavior                                        |
| ------- | ----------------------------------------------- |
| `False` | Data is released after upload.                  |
| `True`  | Data remains accessible through `texture.data`. |

Keeping data in memory can be useful when textures need to be inspected or reused CPU-side later.

---

## Image Scaling

A global texture size limit is configured through:

```python
Texture.MAX_TEXTURE_SIZE
```

Oversized images are automatically downscaled before upload.

This is used to retain compatability with systems with lower texture size limits.

---

## GPU Upload Process

Textures are uploaded lazily.

Creating a texture object does not immediately allocate GPU resources.

Actual OpenGL resources are created when:

```python
texture.use()
```

or

```python
texture.get_id()
```

is called for the first time.

This reduces overhead and avoids uploading unused textures.

---

## Persistent Upload Buffers

The texture system uses a persistently mapped Pixel Buffer Object (PBO).

Advantages:

* Fast texture updates
* Reduced CPU-GPU synchronization
* Efficient streaming of weather data
* No repeated buffer allocation

When a texture is updated, the new data is copied into the mapped buffer and transferred directly to GPU memory.

This approach is significantly more efficient than repeatedly recreating textures.

---

## Updating Existing Textures

Dynamic textures can be updated without recreating the OpenGL texture object.

Example:

```python
texture.update_data(
    new_weather_data
)
```

The texture will automatically refresh its GPU contents.

If the new data changes:

* Resolution
* Channel count
* Data type

the texture is automatically recreated using the new format.

---

## Data Orientation

Texture data is automatically flipped vertically during upload.

This is necessary because:

```text
NumPy:
(0,0) = top-left

OpenGL:
(0,0) = bottom-left
```

The texture class transparently handles this conversion.

Weather repositories and image loaders therefore do not need to perform any manual vertical flipping.

---

## Using Textures

Textures can be bound either through a mesh or directly to a shader.

### Shader Textures

Shader textures are global to a shader and are shared by all drawables rendered with that shader.

Example:

```python
shader.textures["weatherMap"] = weather_texture
```

Inside the shader:

```glsl
uniform sampler2D weatherMap;
```

Texture units are assigned automatically during rendering.

---

### Mesh Textures

Meshes can also own textures independently of the shader.

Example:

```python
mesh.textures["diffuse"] = globe_texture
mesh.textures["normal"] = globe_normal_texture
```

When rendered, mesh textures are exposed through the shader's material structure:

```glsl
struct Material
{
    sampler2D diffuse;
    sampler2D normal;
};

uniform Material material;
```

and can be accessed as:

```glsl
vec4 color = texture(material.diffuse, texCoord);
```

---

### Texture Unit Assignment

Shader textures are bound first:

```python
shader.textures["weatherMap"] = weather_texture
```

Mesh textures are then assigned to the next available texture units automatically.

For example:

```python
shader.textures["weatherMap"] = weather_texture

mesh.textures["diffuse"] = globe_texture
mesh.textures["normal"] = globe_normal_texture
```

may result in:

| Texture | Unit |
|----------|------|
| `weatherMap` | 0 |
| `material.diffuse` | 1 |
| `material.normal` | 2 |

No manual texture-unit management is required.

This allows shader-wide resources and object-specific material textures to coexist without conflicts.

---

## Empty Fallback Textures

The class provides built-in fallback textures that are used whenever a texture is unavailable.

### Empty Color Texture

```python
Texture.empty()
```

Returns a 1×1 white RGBA texture.

Useful as a placeholder for missing color maps.

---

### Empty Normal Map

```python
Texture.empty_normal()
```

Returns a 1×1 flat normal map:

```text
RGB = (128, 128, 255)
```

representing a surface with no perturbation.

Useful as a fallback normal map for lighting shaders.

---

## Resource Management

GPU resources should be released when no longer needed:

```python
texture.delete()
```

This releases:

* OpenGL texture objects
* Pixel Buffer Objects
* Persistent memory mappings

Destroyed textures automatically fall back to a safe placeholder texture if accidentally used afterwards, but it will complain loudly in the console about it.

