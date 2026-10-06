from abc import ABC
from typing import override

from ui.components.base_component import Component


class GenericComponent(Component):
    def __init__(self, render_content=None):
        Component.__init__(self)
        self.content = render_content or (lambda: None)

    @override
    def render(self):
        self.content()


class DateTimeComponent(Component, ABC):
    """Capability tag for components whose ViewModel exposes a date range."""


class GeoPosComponent(Component, ABC):
    """Capability tag for components whose ViewModel exposes a position."""
