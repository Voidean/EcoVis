# Scene Controller

The `SceneController` acts as the central coordinator between the rendering system, user interface, input handling, and data streaming services. While the `Scene` is responsible for rendering objects, the `SceneController` is responsible for updating them.

## Responsibilities

The controller manages:

- Camera movement and navigation
- Synchronization of UI settings with the scene
- Weather and power data streaming
- Wind particle simulation
- Time progression and animation updates
- Astronomical object positioning (sun, moon, sky)
- Runtime rendering settings
- User interactions such as measurement point placement

## Runtime Updates

Each frame, the controller:

1. Updates camera movement from user input
2. Advances simulation time
3. Updates weather and power data streams
4. Updates wind particle simulations
5. Applies changed render settings
6. Updates animated scene objects

## Scene Synchronization

The controller translates application state into rendering state. For example:

- UI selections are applied to shaders
- Weather textures are connected to globe rendering
- Power plant visibility is updated
- MSAA and particle settings are reconfigured
- Projection mode changes affect scene appearance

## Data Integration

The controller connects the rendering system to external repositories through:

- `WeatherDataStreamer`
- `PowerDataStreamer`

These services continuously provide updated textures and datasets that are visualized by the scene.

## User Interaction

The controller also handles scene interactions such as:

- Camera control
- Measurement point placement
- Object selection via mouse clicks

Screen-space mouse coordinates are converted into world-space positions before being passed to the UI systems.

## Design

A key responsibility of the `SceneController` is keeping rendering code independent from application-specific logic. The rendering system only knows how to draw objects, while the controller decides *what* should be shown, *when* it should be updated, and *how* it should react to user input and data changes.