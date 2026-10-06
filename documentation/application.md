# Application Class

The `App` class serves as the central application bootstrapper and runtime manager.

It is responsible for:

* Creating and configuring the OpenGL context
* Creating the application window
* Initializing ImGui
* Loading the scene
* Managing the render loop
* Handling window events and resizing
* Coordinating rendering, UI updates, and user input
* Managing application shutdown and resource cleanup

Importantly, the `App` class is intentionally **decoupled from any domain-specific logic**. It does not contain weather visualization code, data processing logic, or rendering details for individual scene objects. Instead, it acts as a generic application framework that orchestrates the interaction between the rendering system, user interface, input handling, and scene management components.

---

## Responsibilities

The class can be viewed as the top-level coordinator of the application.

```text
App
├── GLFW Window
├── OpenGL Context
├── Frame Buffer
├── ImGui Renderer
├── Input System
├── Scene
├── Scene Controller
└── UI Manager
```

Each subsystem is initialized once and then managed throughout the application's lifetime.

---

## OpenGL Initialization

The application begins by creating a GLFW window and OpenGL context.

During initialization, several OpenGL features are enabled:

| Feature              | Purpose                                            |
| -------------------- | -------------------------------------------------- |
| Blending             | Supports transparency.                             |
| Multisampling        | Anti-aliasing for smoother edges.                  |
| Line Smoothing       | Improved rendering of line primitives.             |
| Primitive Restart    | Allows efficient rendering of complex line strips. |
| OpenGL Debug Context | Optional runtime debugging.                        |

The application also queries the maximum supported texture size:

```python
Texture.MAX_TEXTURE_SIZE = glGetIntegerv(GL_MAX_TEXTURE_SIZE)
```

This value is later used by the texture system to avoid creating unsupported textures.

---

## ImGui Integration

The application creates and configures the ImGui context.

```python
imgui.create_context()
```

A GLFW-backed renderer is then attached:

```python
GlfwRenderer(window)
```

The current display scaling factor is applied automatically to ensure that the user interface remains readable on high-DPI displays.

ImGui state is persisted using a configuration file, allowing window layouts and settings to be restored between application launches.

---

## Scene Loading

The scene is created through the `SceneBuilder`.

```python
scene = scene_builder()
```

Loading can be an expensive operation due to:

* Mesh generation
* Texture loading
* Shader compilation
* Weather data preparation

For this reason the builder exposes progress updates through a generator interface.

During loading, a dedicated loading screen is rendered to provide feedback to the user.

```text
Loading Screen
       ↓
Scene Builder
       ↓
Finished Scene
```

Once loading is complete, the camera is initialized with the current framebuffer size and display scaling information.

---

## Scene Controller Integration

After scene creation, a `SceneController` is instantiated.

```python
SceneController(
    scene,
    ui_manager,
    frame_buffer,
    input
)
```

The controller contains the application-specific logic and updates the scene in response to:

* User input
* Time progression
* UI interactions
* Data changes

The `App` itself remains unaware of these details.

---

## Window Event Handling

The application registers several GLFW callbacks.

### Framebuffer Resize

When the window size changes:

```python
framebuffer_size_callback(...)
```

the following components are updated:

* Camera projection matrix
* Framebuffer size

This ensures rendering continues correctly at the new resolution.

---

### Content Scale Changes

When DPI scaling changes:

```python
content_scale_callback(...)
```

the application updates:

* Camera pixel scaling information
* ImGui scaling

This is particularly important on high-resolution displays and when moving the window between monitors with different scaling factors.

---

## Main Render Loop

The application's runtime is managed by a traditional game-loop style render loop.

```text
Poll Events
     ↓
Process Input
     ↓
Update Scene
     ↓
Render Scene
     ↓
Render UI
     ↓
Swap Buffers
```

This sequence is repeated until the application exits.

---

## Delta Time Calculation

The loop measures elapsed time between frames:

```python
delta_time = current_frame - last_frame
```

This value is passed to update systems to ensure that movement and animations remain independent of frame rate.

---

## Input Processing

Every frame:

```python
glfw.poll_events()
```

is called to process window and input events.

The ImGui renderer also receives input updates:

```python
imgui_renderer.process_inputs()
```

allowing UI interactions and scene interactions to coexist seamlessly.

---

## Minimized Window Optimization

When the window is minimized:

```python
glfw.ICONIFIED
```

the application temporarily pauses rendering and sleeps briefly.

```python
time.sleep(0.1)
```

This significantly reduces CPU and GPU usage while the application is not visible.

---

## Scene Updates

Application logic is updated through:

```python
scene_controller.update(delta_time)
```

This may include:

* Camera movement
* Animation updates
* Weather visualization updates
* UI-driven state changes

The specific behavior is determined by the active controller implementation rather than the application framework itself.

---

## Rendering

Scene rendering is performed through:

```python
scene.render(frame_buffer)
```

Internally this:

1. Updates the scene uniform buffer.
2. Renders all visible objects.
3. Resolves multisampled framebuffers.
4. Executes screen-space rendering passes.

The `App` class does not need to know how individual objects are rendered.

---

## User Interface Rendering

After the 3D scene has been rendered, the user interface is drawn.

```python
ui_manager.render(...)
```

followed by:

```python
imgui_renderer.render(...)
```

This separation ensures that UI elements are rendered on top of the scene.

---

## Buffer Swapping

The final rendered image is presented using:

```python
glfw.swap_buffers(window)
```

This swaps the back buffer with the visible front buffer and completes the frame.

---

## Shutdown

When the application exits, all resources are cleaned up in a controlled manner.

The shutdown process releases:

* Scene resources
* OpenGL resources
* Framebuffers
* ImGui resources
* GLFW resources

```python
scene.delete()
scene_controller.destroy()
imgui_renderer.shutdown()
glfw.terminate()
```

Proper cleanup prevents memory leaks and ensures that GPU resources are correctly released.

---

## Design Philosophy

The `App` class intentionally focuses on infrastructure rather than application logic.

Its primary purpose is to provide a reusable framework for:

* Window management
* Rendering
* Input handling
* UI integration
* Resource management

Domain-specific functionality such as weather visualization, data loading, rendering techniques, and user interactions are delegated to specialized components such as the `SceneBuilder`, `SceneController`, repositories, and rendering systems.

This separation of concerns keeps the application architecture modular, maintainable, and easier to extend.
