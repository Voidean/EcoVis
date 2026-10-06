"""Compatibility loader for imgui-bundle's SDL3 backend and PySDL3."""

import ctypes
import sys

from sdl3 import SDL as sdl


# imgui-bundle currently imports SDL symbols from the namespace package root,
# while current PySDL3 exposes them from sdl3.SDL.
_namespace_package = sys.modules.get("sdl3")
sys.modules["sdl3"] = sdl
try:
    from imgui_bundle.python_backends import sdl3_backend as _backend
finally:
    if _namespace_package is None:
        del sys.modules["sdl3"]
    else:
        sys.modules["sdl3"] = _namespace_package


# PySDL3 maps C's int to c_long. They have the same 32-bit layout on the
# supported desktop targets, but the bundled backend passes c_int pointers.
sdl.SDL_GetWindowSize.argtypes = [
    sdl.SDL_GetWindowSize.argtypes[0],
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int),
]

SDL3Renderer = _backend.SDL3Renderer
