"""Common interface for entries managed by the view registry."""

from typing import Protocol

from ui.views.view_types import ViewMetadata


class RegisteredView(Protocol):
    metadata: ViewMetadata

    @property
    def is_retired(self) -> bool: ...

    def render(self, dt): ...

    def destroy(self): ...
