# Scene Builder

The `scene_builder()` function is responsible for constructing the complete application scene during startup. It acts as a centralized initialization pipeline that creates shaders, loads meshes and textures, initializes world objects, loads external datasets, and registers everything with the `Scene`.

The builder is implemented as a generator and periodically yields loading progress updates. This allows the loading screen to display meaningful progress information while large assets are being processed.

## Responsibilities

The scene builder performs the following tasks:

- Compiles and registers all shaders used by the application
- Configures the initial camera position and orientation
- Creates the globe, atmosphere, sky, moon, and cloud models
- Loads country borders and power grid geometry
- Initializes power plant models and animations
- Loads weather and power repositories
- Registers all drawables with the appropriate shaders
- Adds animated objects to the scene animation system
- Returns a fully configured `Scene` object

## Loading Workflow

All vertex and fragment shaders are compiled and registered with the scene.
Screen-space shaders such as the atmosphere effect are registered separately from regular 3D shaders.

The initial camera position is configured before rendering begins.

Then all the assets are loaded and positioned in the scene.

For instance, the Earth mesh is generated from a heightmap using the procedural globe generation system. Since generating the globe geometry is computationally expensive, the mesh is loaded through the mesh cache system.

Once all resources are loaded:

- All drawables have been registered
- Animations have been configured
- Repository data has been initialized
- Textures have been assigned

The fully constructed `Scene` instance is returned.

## Progress Reporting

The function yields progress values throughout the loading process:

```python
yield 0.5, "Loading Border Models..."
```

The application displays these values on the loading screen while initialization is running.

This provides visual feedback during expensive startup operations such as:

- Shader compilation
- Mesh generation
- Texture loading
- Power plant processing
- Dataset loading
