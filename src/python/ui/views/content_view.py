"""A minimal ImGui window around one reusable component."""

from collections.abc import Callable
from typing import TypeAlias

from ui.components.base_component import Component
from ui.views.view_types import ViewMetadata
from ui.views.window_view import WindowView


ComponentFactory: TypeAlias = Callable[[], Component]


class ContentView(WindowView):
    """Provide window lifecycle and chrome for exactly one component."""

    def __init__(
            self,
            metadata: ViewMetadata,
            component: Component,
            *,
            component_factory: ComponentFactory | None = None,
            destroy_on_close: bool = True,
    ):
        if not isinstance(component, Component):
            raise TypeError("ContentView expects a Component")
        self.component = component
        self._component_factory = component_factory or type(component)
        super().__init__(
            metadata,
            preferred_size=component.preferred_size or (700, 625),
            destroy_on_close=destroy_on_close,
        )

    def render_content(self):
        self.component.render()

    def hide_content(self):
        self.component.hide()

    def destroy_content(self):
        self.component.destroy()

    def recreate(self):
        component = self._component_factory()
        if not isinstance(component, Component):
            raise TypeError("A component factory must return a Component")
        return type(self)(
            self.metadata,
            component,
            component_factory=self._component_factory,
            destroy_on_close=self.destroy_on_close,
        )
