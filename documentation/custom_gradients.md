### Custom Gradients

Additional color gradients for scalar weather data can be added to:

```text
resources/textures/gradients/
```

Each gradient is loaded from an image file and mapped from left to right:

- Left edge → lower data values
- Right edge → higher data values

A height of 1 pixel is sufficient, as only the horizontal color distribution is used.

The gradient's display name is derived from the filename without its extension. For example:
```text
resources/textures/gradients/My Gradient.png
```
will appear in the application as:
```text
My Gradient
```