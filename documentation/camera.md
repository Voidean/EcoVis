# Camera

The `Camera` class represents the viewer's position and orientation within the 3D scene.

It is responsible for:

* Managing camera position and rotation
* Generating view and projection matrices
* Handling viewport changes
* Calculating frustum planes
* Performing frustum culling checks

The camera is stored in the `Scene` object and its matrices are uploaded to the `SceneUBO`, making them available to all shaders.

---

## Overview

The camera stores:

| Property               | Purpose                                 |
| ---------------------- | --------------------------------------- |
| `translation`          | World-space camera position.            |
| `yaw`                  | Horizontal rotation angle.              |
| `pitch`                | Vertical rotation angle.                |
| `fov`                  | Field of view in degrees.               |
| `front`                | Forward viewing direction. Read only.   |
| `right`                | Right direction vector. Read only.      |
| `view_transform`       | View matrix.                            |
| `projection_transform` | Projection matrix.                      |
| `frustum_planes`       | Cached frustum planes used for culling. |

---

## Camera Coordinate System

The camera uses a standard right-handed coordinate system.

Initial orientation:

```text
Position: (0, 0, 0)

Forward (+Z)
Up      (+Y)
Right   (+X)
```

The default yaw of 90° causes the camera to initially look along the positive Z-axis.

---

## Initialization

Before the camera can be used, it must be initialized with the current viewport size and display scaling information.

```python
camera.initialize(
    viewport_size=(width, height),
    content_scale=(scale_x, scale_y)
)
```

This initializes:

* View matrix
* Projection matrix
* Aspect ratio
* Pixel scaling factors

---

## View Matrix

The view matrix describes the camera's position and orientation in the world.

Whenever the camera moves or rotates:

```python
camera.apply_view_transform()
```

must be called.

It is generated using:

```python
glm.lookAt(...)
```

The resulting matrix transforms world-space coordinates into camera-space coordinates.

---

## Camera Rotation

Camera rotation is controlled using:

| Property | Description                                   |
| -------- | --------------------------------------------- |
| `yaw`    | Horizontal rotation around the world up axis. |
| `pitch`  | Vertical look angle.                          |

The forward vector is calculated from spherical coordinates:

```text
front.x = cos(yaw) * cos(pitch)
front.y = sin(pitch)
front.z = sin(yaw) * cos(pitch)
```

This allows smooth first-person style camera movement without requiring rotation matrices.

---

## Projection Matrix

The projection matrix controls how the 3D world is projected onto the screen.

It is generated using:

```python
glm.perspective(...)
```

with:

* Field of View (`fov`)
* Aspect Ratio
* Near Plane = 0.1
* Far Plane = 500.0

The matrix is recalculated whenever:

* Window size changes
* Field of view changes

---

## Field of View

The field of view can be adjusted dynamically.

```python
camera.set_fov(60.0)
```

A larger field of view:

* Shows more of the world
* Increases perspective distortion

A smaller field of view:

* Zooms in
* Produces a more orthographic appearance

---

## Viewport Handling

Whenever the application window changes size:

```python
camera.set_viewport_size(
    width,
    height
)
```

should be called.

The camera automatically recalculates:

```text
Aspect Ratio
       ↓
Projection Matrix
       ↓
Frustum Planes
```

to match the new viewport dimensions.

---

## Frustum Culling

One of the camera's most important responsibilities is determining whether an object is visible.

To achieve this, the camera extracts the six planes of the viewing frustum:

```text
Left
Right
Bottom
Top
Near
Far
```

These planes form the visible volume of the camera.

Objects outside this volume do not need to be rendered.

---

## Frustum Plane Extraction

Whenever the view or projection matrix changes, the camera calculates:

```text
Projection Matrix
        ×
View Matrix
        ↓
View-Projection Matrix
        ↓
Frustum Planes
```

The six clipping planes are extracted directly from the combined view-projection matrix.

Each plane is stored in the form:

```text
Ax + By + Cz + D = 0
```

and normalized for efficient distance calculations.

The resulting planes are cached in:

```python
camera.frustum_planes
```

---

## Visibility Testing

The method:

```python
camera.cull_frustum(
    position,
    radius
)
```

performs a simple sphere-frustum intersection test.

Parameters:

| Parameter  | Description                       |
| ---------- | --------------------------------- |
| `position` | World-space center of the object. |
| `radius`   | Bounding sphere radius.           |

For each frustum plane:

```text
distance = dot(normal, position) + D
```

If the sphere lies completely outside any plane:

```text
distance < -radius
```

the object is considered invisible.

Otherwise it is rendered.

---

## Integration with Models

The `Model` class automatically performs frustum culling before drawing:

```python
if not camera.cull_frustum(
        self.entity.translation,
        self.get_bounding_radius()
):
    return
```

This prevents unnecessary draw calls for objects outside the camera view.

For large scenes this can significantly improve rendering performance.

---

## Integration with the Scene

During rendering, the camera matrices are uploaded into the `SceneUBO`.

```python
scene.ubo.update_view_matrices(camera)
```

The following matrices become available to all shaders:

| Matrix                | Purpose                     |
| --------------------- | --------------------------- |
| View                  | Camera transform.           |
| Projection            | Perspective projection.     |
| ViewProjection        | Combined matrix.            |
| ViewNoTranslation     | Skybox rendering.           |
| InverseViewProjection | World-space reconstruction. |

Additionally, the camera position is uploaded for lighting and atmospheric calculations.

---

## Change Tracking

The camera maintains a `changed` flag.

Whenever:

* Position changes
* Rotation changes
* FOV changes
* Viewport size changes

the flag is set.

This allows the `SceneUBO` to update GPU data only when necessary, avoiding unnecessary uploads every frame.

---

## Typical Usage

```python
camera.translation += movement
camera.yaw += yaw_delta
camera.pitch += pitch_delta

camera.apply_view_transform()
```

During rendering:

```python
scene.ubo.update_view_matrices(camera)
```

The camera then provides:

* View matrix generation
* Projection matrix generation
* Frustum culling
* Shader camera data

for the entire rendering pipeline.
