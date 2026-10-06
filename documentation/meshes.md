# Meshes

## Mesh Data

Geometry is represented by the `MeshData` class before it is uploaded to the GPU.

A mesh consists of:

- Vertices
- Triangle indices

Each vertex stores the following attributes:

| Attribute | Description |
|------------|-------------|
| Position | 3D position in model space |
| Tangent | Tangent vector for normal mapping |
| Bitangent | Bitangent vector for normal mapping |
| Normal | Surface normal |
| Color | Vertex color |
| UV | Texture coordinates |

Internally, the data is converted into a compact vertex buffer layout containing:

```text
Position   : vec3
Tangent    : vec3
Bitangent  : vec3
Normal     : vec3
Color      : vec4
UV         : vec2
```

for a total of 18 floating-point values per vertex.

---

### Automatic Normal and Tangent Generation

`MeshData` provides:

```python
mesh_data.generate_normals_and_tangents()
```

which automatically calculates:

- Vertex normals
- Tangents
- Bitangents

from the mesh geometry and UV coordinates.

The generated tangent space vectors are orthogonalized to ensure correct lighting and normal mapping.

---

## Mesh Objects

The `Mesh` class represents geometry that has already been uploaded to the GPU.

When a mesh is created:

```python
mesh = Mesh(mesh_data)
```

the following OpenGL objects are generated:

- Vertex Array Object (VAO)
- Vertex Buffer Object (VBO)
- Element Buffer Object (EBO)

The mesh then becomes ready for rendering.

---

### Mesh Textures

Meshes can store their own material textures.

By default, every mesh contains:

| Texture | Purpose |
|----------|---------|
| `diffuse` | Base color texture |
| `normalMap` | Surface normal map |

Additional textures can be added as needed:

```python
mesh.textures["roughness"] = roughness_texture
mesh.textures["ao"] = ao_texture
```

During rendering, mesh textures are automatically exposed to shaders through the material structure:

```glsl
struct Material
{
    sampler2D diffuse;
    sampler2D normalMap;
    sampler2D roughness;
    sampler2D ao;
};

uniform Material material;
```

and can be accessed as:

```glsl
vec4 color = texture(material.diffuse, uv);
```

---

## Loading Models

Meshes can be imported directly from model files using:

```python
mesh = Mesh.from_file("globe")
```

The loader uses `trimesh` and currently supports the `.obj` format.
If a model contains multiple submeshes, they are automatically combined into a single mesh.

### Automatic Texture Loading

When loading a model, the loader automatically searches for common texture files in the model directory.

Supported naming conventions include:

| Material Slot | Supported Filenames |
|---------------|--------------------|
| Normal Map | `normal.jpg`, `normal.png`, `norm.jpg` |
| Roughness | `roughness.jpg`, `roughness.png`, `rough.jpg` |
| Specular | `specular.jpg` |
| Ambient Occlusion | `ao.jpg`, `ao.png`, `ambientocclusion.jpg` |

For example:

```text
models/
└── earth/
    ├── earth.obj
    ├── diffuse.jpg
    ├── normal.jpg
    ├── roughness.jpg
    └── ao.jpg
```

will automatically load the available textures and assign them to the mesh.

---

## Mesh Cashing

The meshes of complex static objects like the globe model are only created the first time the application starts. Mapping the 2D texture onto a 3D sphere and also applying a heightmap to the vertices is quite a computational effort.
For this reason, the result is saved as a processed .npz file that can be directly loaded as a model to the GPU in subsequent runs of the application.
This decreases the time spent in the loading screen significantly.

Procedural meshes can be cached using the mesh cache service:

```python
from service.mesh_cache import load_geometry
```

Instead of regenerating geometry every startup, generated vertex and index data can be stored as compressed NumPy files.

Example:

```python
vertices, indices = load_mesh_data("globe", create_globe, 500, heightmap)
```

The first application run will:

1. Generate the mesh
2. Convert it into GPU-ready arrays
3. Save it as a compressed cache file

Subsequent runs will load the cached data directly.


### Cache Location

Cached meshes are stored in:

```text
cache/mesh_cache/
```

using the format:

```text
<mesh_name>_<hash>.npz
```

For example:

```text
globe_46890d2cc54d4999.npz
```

### Cache Hashing

Cache files are identified using a hash generated from:

- Generator parameters
- Keyword arguments
- Cache version

This ensures that changing generation settings automatically creates a new cache entry.


### Cache Versioning

The cache system supports explicit versioning.

Increasing the version number invalidates all previously generated cache files for that mesh configuration.

This is useful whenever:

- Vertex layouts change
- UV generation changes
- Mesh generation algorithms change

without requiring manual cache cleanup.


### Recommended Usage

Mesh caching is most beneficial for geometry that is:

- Computationally expensive to generate
- Deterministic
- Static after generation

Examples include:

- Large procedurally generated models
- Heightmap-displaced geometry
- Globe mesh
- Borders, coastlines and power data line meshes

Small or frequently changing meshes generally do not benefit significantly from caching.