## Configuration using config.json

Application settings are loaded from `config.json` in the project root. Missing values are automatically filled from the default configuration, allowing users to override only the settings they want to change.

### Example Config

```json
{
  "window": {
    "show_fps": true
  },

  "keybinds": {
    "orbital_move_farther": "KEY_DOWN",
    "orbital_move_closer": "KEY_UP",
    "orbital_move_up": "KEY_RIGHT_SHIFT",
    "orbital_move_down": "KEY_RIGHT_CONTROL",
    "orbital_move_left": "KEY_LEFT",
    "orbital_move_right": "KEY_RIGHT",

    "move_forward": "KEY_UP",
    "move_back": "KEY_DOWN",
    "move_left": "KEY_LEFT",
    "move_right": "KEY_RIGHT",
    "move_up": "KEY_RIGHT_SHIFT",
    "move_down": "KEY_RIGHT_CONTROL",

    "rotate_left": "KEY_A",
    "rotate_right": "KEY_D",
    "rotate_up": "KEY_W",
    "rotate_down": "KEY_S"
  }
}
```

### Window

Controls the application window. 

Category name: `window`

| Value               | Default | Description |
|---------------------|----------|-------------|
| `title`             | `EcoVis` | Window title. |
| `width`             | `1920` | Initial window width in pixels. |
| `height`            | `1080` | Initial window height in pixels. |
| `enable_ui_scaling` | `false` | Enables automatic UI scaling based on display DPI. |
| `show_fps`          | `false` | Displays the current frame rate on screen. |

### OpenGL

Controls OpenGL-related options.

Category name: `opengl`

| Value | Default | Description |
|----------|----------|-------------|
| `debug` | `false` | Enables OpenGL debug output and validation messages. |

### Input

Controls camera and navigation sensitivity.

Category name: `input`

| Value | Default | Description |
|----------|----------|-------------|
| `key_step_size` | `10.0` | Movement speed for keyboard controls. |
| `mouse_sensitivity` | `0.002` | Mouse look sensitivity. |
| `scroll_speed` | `2.0` | Zoom speed when using the mouse wheel. |

### Keybinds

Maps application actions to GLFW key constants.

Supported actions include:

- Orbital camera movement
- Free camera movement
- Camera rotation
- Zoom controls
- Fullscreen toggle
- Wireframe rendering toggle
- Camera mode toggle

Key names must match valid GLFW key constants (e.g. `KEY_W`, `KEY_SPACE`, `KEY_F11`).

Category name: `keybinds`

| Value | Default | Description |
|----------|-----------|-------------|
| `orbital_move_farther` | `KEY_SPACE` | Move the orbital camera farther from the target. |
| `orbital_move_closer` | `KEY_LEFT_CONTROL` | Move the orbital camera closer to the target. |
| `orbital_move_up` | `KEY_W` | Move the orbital camera upward. |
| `orbital_move_down` | `KEY_S` | Move the orbital camera downward. |
| `orbital_move_left` | `KEY_A` | Move the orbital camera left. |
| `orbital_move_right` | `KEY_D` | Move the orbital camera right. |
| `move_forward` | `KEY_W` | Move the free camera forward. |
| `move_back` | `KEY_S` | Move the free camera backward. |
| `move_left` | `KEY_A` | Move the free camera left. |
| `move_right` | `KEY_D` | Move the free camera right. |
| `move_up` | `KEY_SPACE` | Move the free camera upward. |
| `move_down` | `KEY_LEFT_CONTROL` | Move the free camera downward. |
| `rotate_left` | `KEY_LEFT` | Rotate the camera left. |
| `rotate_right` | `KEY_RIGHT` | Rotate the camera right. |
| `rotate_up` | `KEY_UP` | Rotate the camera upward. |
| `rotate_down` | `KEY_DOWN` | Rotate the camera downward. |
| `zoom_in` | `KEY_PAGE_UP` | Increase zoom level. |
| `zoom_out` | `KEY_PAGE_DOWN` | Decrease zoom level. |
| `toggle_fullscreen` | `KEY_F11` | Toggle fullscreen mode. |
| `toggle_wireframe` | `KEY_U` | Toggle wireframe rendering. |
| `toggle_camera` | `KEY_C` | Switch between available camera modes. |

### Configuration Loading

At startup, the application loads the default configuration and merges any values found in the user configuration file. User-defined values override the defaults while unspecified settings continue to use their default values.