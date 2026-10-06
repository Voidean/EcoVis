from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class Drawable(ABC):
    def __init__(self):
        self.hidden = False
        self.shader_uniforms: dict[str, Any | Callable[[], Any]] = {}

    def apply_shader_uniforms(self, shader, defaults=None):
        for name, value in (defaults or {}).items():
            val = value() if callable(value) else value
            shader.set_uniform(name, val)
        for name, value in self.shader_uniforms.items():
            val = value() if callable(value) else value
            shader.set_uniform(name, val)

    @abstractmethod
    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        pass

    @abstractmethod
    def delete(self):
        pass
