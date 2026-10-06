# Input System

The application uses a centralized input system that abstracts GLFW keyboard and mouse events into a simple interface that can be consumed by other systems. Rather than directly coupling rendering or application logic to GLFW callbacks, the `Input` class stores the current input state and distributes events to interested components through a lightweight event system.

## Responsibilities

The input system is responsible for:

- Tracking keyboard state (`keys_down`)
- Tracking mouse position and scroll input
- Detecting mouse drags and clicks
- Managing cursor capture during drag operations
- Handling application-wide shortcuts (fullscreen, wireframe mode)
- Forwarding input events to registered listeners
- Integrating with ImGui so that UI interactions do not trigger application controls

Because all input passes through a single location, other systems can simply query the current state instead of registering their own GLFW callbacks.

## Event Handling

The class installs GLFW callbacks for:

- Keyboard input
- Mouse button events
- Mouse movement
- Mouse wheel scrolling

Existing GLFW callbacks (such as those used by ImGui) are preserved through callback chaining, ensuring that multiple systems can receive the same events.

Input events are only forwarded to the application when ImGui is not actively capturing keyboard or mouse input. This prevents camera movement or scene interactions while the user is editing UI controls.

## Keyboard State

The currently pressed keys are stored in the `keys_down` set.

This allows systems such as camera controls to continuously check whether movement keys are currently held down rather than reacting only to discrete key presses.

Example:

```python
if KEYBINDS["move_forward"] in input.keys_down:
    ...
```

## Mouse Interaction

The input system tracks:

- Current mouse position
- Drag start position
- Drag delta between frames
- Active drag button
- Scroll wheel movement

When either the left or right mouse button is pressed, the cursor is captured and hidden. While dragging, the system continuously records mouse movement deltas.

When the button is released:

- Small movements are treated as clicks
- Larger movements are treated as drag operations

This distinction allows the same mouse button to be used both for object selection and camera manipulation.

## Event Listeners

Other systems can subscribe to input events through simple callback lists:

```python
input.mouse_click_handlers.append(handler)
input.key_press_handlers.append(handler)
```

This keeps the input layer independent of application-specific functionality.

For example:

- The scene controller registers mouse click handlers for measurement points.
- The camera movement system registers key handlers to switch movement modes.

## Camera Controls

The primary consumer of the input system is the `CameraMovement` component.

`CameraMovement` interprets keyboard, mouse drag, and scroll events and converts them into camera transformations. Depending on the current projection mode, it supports:

- Free-flying camera movement
- Globe orbit controls
- Map-style navigation

The input system itself remains unaware of these behaviours and only provides raw input information. This separation keeps input handling independent from camera logic and allows alternative control schemes to be implemented without modifying the underlying input layer.

## Decoupled Design

A key design goal is separation of concerns.

The `Input` class does not know anything about:

- Cameras
- Rendering
- Domain specific logic
- Scene objects
- User interface windows

It only records and distributes user input.

Higher-level systems subscribe to input events or query the stored state, allowing input handling to remain reusable and independent from application-specific logic.