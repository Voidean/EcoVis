"""Base Component for reversible compositions of child Components."""

from abc import ABC
from collections.abc import Sequence

from typing_extensions import override

from ui.components.base_component import Component


class CompositeComponent(Component, ABC):
    """A merged Component which owns its child Components until released."""

    def __init__(self, components: Sequence[Component]):
        super().__init__()
        self._components = list(components)
        preferred_sizes = [
            component.preferred_size
            for component in self._components
            if component.preferred_size is not None
        ]
        if preferred_sizes:
            self.preferred_size = (
                max(size[0] for size in preferred_sizes),
                max(size[1] for size in preferred_sizes),
            )

    @property
    def components(self) -> tuple[Component, ...]:
        return tuple(self._components)

    def release_components(self) -> list[Component]:
        """Give ownership of all children back to a component container."""
        components = self._components
        self._components = []
        return components

    @override
    def update(self, **kwargs):
        for component in self._components:
            component.update(**kwargs)

    @override
    def hide(self):
        for component in self._components:
            component.hide()

    @override
    def destroy(self):
        for component in self._components:
            component.destroy()
        self._components.clear()
        super().destroy()
