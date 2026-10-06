# Frame Buffers

The `FrameBuffer` class provides an abstraction around OpenGL Framebuffer Objects (FBOs).

It can also be used whenever rendering should be performed into textures instead of directly to the screen.

The class manages both color and depth attachments and automatically handles multisample resolve operations when MSAA is enabled.

---

## Basic Usage

A framebuffer can be created as follows:

```python
frame_buffer = FrameBuffer(
    width=1920,
    height=1080
)
```

To render into it:

```python
frame_buffer.bind()
```

After rendering:

```python
frame_buffer.copy_to_screen()
```

or use its textures for further rendering passes.

---

## Internal Structure

A framebuffer consists of:

| Component             | Purpose                                        |
| --------------------- | ---------------------------------------------- |
| Main FBO              | Receives all rendering output.                 |
| Color Texture         | Stores rendered color data.                    |
| Depth Texture         | Stores depth information.                      |
| Resolve FBO           | Stores resolved textures when MSAA is enabled. |
| Resolve Color Texture | Non-multisampled color texture.                |
| Resolve Depth Texture | Non-multisampled depth texture.                |

For non-MSAA rendering only the main framebuffer is required.

When MSAA is enabled, an additional resolve framebuffer is automatically created.

---

## Color Attachments

The framebuffer always contains a color attachment.

The texture format can be selected during creation:

```python
FrameBuffer(
    width,
    height,
    color_internal_format=GL_RGBA16F
)
```

Common formats include:

| Format       | Description                         |
| ------------ | ----------------------------------- |
| `GL_RGBA8`   | Standard 8-bit color buffer.        |
| `GL_RGBA16F` | Half-float HDR rendering.           |
| `GL_RGBA32F` | Full-float HDR rendering.           |
| `GL_R16F`    | Single-channel floating-point data. |
| `GL_RG16F`   | Two-channel floating-point data.    |

This allows the framebuffer to be used for both visual rendering and numerical GPU processing.

---

## Depth Attachments

Depth rendering can be enabled or disabled.

```python
FrameBuffer(
    width,
    height,
    use_depth=True
)
```

When enabled, a depth texture is created and attached to the framebuffer.

Depth textures are useful for:

* Depth testing
* Atmosphere rendering
* Screen-space effects
* Depth reconstruction

---

## Multisample Anti-Aliasing (MSAA)

The framebuffer supports multisampled rendering.

Example:

```python
frame_buffer = FrameBuffer(
    width,
    height,
    samples=4
)
```

When `samples > 1`:

1. Rendering occurs into multisampled textures.
2. The framebuffer cannot be sampled directly by shaders.
3. The result must be resolved into standard textures.

Internally this creates:

```text
Main FBO
├── Multisampled Color Texture
└── Multisampled Depth Texture

Resolve FBO
├── Standard Color Texture
└── Standard Depth Texture
```

The resolve step is performed automatically through:

```python
frame_buffer.resolve()
```

which copies the multisampled result into standard textures.

---

## Rendering Workflow

A typical rendering sequence looks like:

```python
frame_buffer.bind()

# Render scene

frame_buffer.resolve()
frame_buffer.copy_to_screen()
```

Internally:

```text
Scene
   ↓
Main FBO
   ↓
Resolve FBO (MSAA only)
   ↓
Screen
```

This is also the workflow used by the scene renderer.

---

## Accessing Rendered Textures

The framebuffer exposes its color and depth textures.

### Color Texture

```python
color_tex = frame_buffer.get_color_texture()
```

Returns:

* Resolve texture when MSAA is enabled
* Main color texture otherwise

This ensures shaders always receive a standard `GL_TEXTURE_2D`.

---

### Depth Texture

```python
depth_tex = frame_buffer.get_depth_texture()
```

Returns the depth texture that can be sampled by shaders.

Typical usage:

```glsl
uniform sampler2D depthMap;
```

This is used by atmosphere and post-processing shaders.

---

## Binding Textures to Shaders

The framebuffer can bind its textures directly to texture units.

### Color

```python
frame_buffer.bind_color_to_unit(0)
```

Shader:

```glsl
uniform sampler2D colorMap;
```

---

### Depth

```python
frame_buffer.bind_depth_to_unit(0)
```

Shader:

```glsl
uniform sampler2D depthMap;
```

This simplifies the use of framebuffer textures in fullscreen rendering passes.

---

## Screen-Space Rendering

After the main scene has been rendered, framebuffer textures can be used for additional rendering passes.

Typical workflow:

```text
Render Scene
    ↓
Render Post Processing (Atmosphere)
    ↓
Present Final Image
```

Screen-space shaders typically can sample the Color texture and Depth texture to generate the final image.

---

## Resizing

Framebuffers can be resized dynamically.

```python
frame_buffer.update_size(
    width,
    height
)
```

This recreates all internal textures using the new dimensions.

This is typically performed when:

* The application window changes size
* Resolution scaling changes
* MSAA settings change

The framebuffer automatically clamps dimensions to:

```python
Texture.MAX_TEXTURE_SIZE
```

to prevent unsupported texture allocations.

---

## Changing MSAA Samples

The sample count can be modified at runtime.

```python
frame_buffer.set_samples(8)
```

The framebuffer will automatically recreate all attachments with the new sample count.

This allows anti-aliasing quality to be changed without recreating the framebuffer object manually.

---

## Texture Wrapping

Texture wrapping behavior can be configured during creation.

```python
FrameBuffer(
    width,
    height,
    repeat_s=True,
    repeat_t=True
)
```

| Setting    | Description                  |
| ---------- | ---------------------------- |
| `repeat_s` | Horizontal texture wrapping. |
| `repeat_t` | Vertical texture wrapping.   |

By default, framebuffer textures use:

```python
repeat_s=False
repeat_t=False
```

which corresponds to:

```cpp
GL_CLAMP_TO_EDGE
```

and prevents sampling artifacts at texture borders.

---

## Reading Depth Values

The framebuffer allows reading individual depth values from the GPU.

```python
depth = frame_buffer.read_depth_pixel(
    mouse_x,
    mouse_y
)
```

Internally this uses:

```cpp
glReadPixels(...)
```

to retrieve the depth buffer value at a specific screen position.

Applications include:

* Mouse picking
* World position reconstruction
* Object selection

---

## Resource Management

Framebuffers own several OpenGL resources:

* Framebuffer Objects (FBOs)
* Color textures
* Depth textures
* Resolve textures

Whenever the framebuffer is resized, obsolete textures are automatically released.

The internal cleanup routine ensures that old GPU resources do not accumulate during runtime.

Proper framebuffer management is particularly important for high-resolution rendering where color and depth attachments can consume significant amounts of GPU memory.
