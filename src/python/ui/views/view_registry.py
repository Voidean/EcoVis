from collections.abc import Iterator

from model.state.view_state import ViewState
from ui.views.registered_view import RegisteredView
from ui.views.view_types import ViewId


class ViewRegistry:
    """Owns application views and exposes UI navigation by stable view ID."""

    def __init__(self, state: ViewState):
        self._state = state
        self._views: dict[ViewId, RegisteredView] = {}

    def register(self, view_id: ViewId, view: RegisteredView):
        self._views[view_id] = view
        self._state.enabled_views.setdefault(view_id, False)

    def menu_options(
            self,
            view_ids: set[ViewId],
    ) -> tuple[tuple[ViewId, str, bool], ...]:
        return tuple(
            (
                view_id,
                self._views[view_id].metadata.title,
                self._state.enabled_views.get(view_id, False),
            )
            for view_id in self._state.enabled_views
            if view_id in view_ids and view_id in self._views
        )

    def set_enabled(self, view_id: ViewId, enabled: bool):
        if enabled:
            self._restore_if_needed(view_id)
        self._state.enabled_views[view_id] = enabled

    def enabled_items(self) -> Iterator[tuple[ViewId, RegisteredView]]:
        for view_id, view in self._views.items():
            if self._state.enabled_views.get(view_id, False):
                yield view_id, view

    def values(self) -> tuple[RegisteredView, ...]:
        return tuple(self._views.values())

    def clear(self):
        self._views.clear()

    def _restore_if_needed(self, view_id: ViewId):
        view = self._views[view_id]
        if view.is_retired:
            recreate = getattr(view, "recreate", None)
            if recreate is None:
                raise TypeError("A retired registered view must be recreatable")
            self._views[view_id] = recreate()
