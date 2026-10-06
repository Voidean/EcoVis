from typing import Protocol

from model.state.render_state import render_state
from model.state.view_state import ViewState, view_state
from ui.view_model import ViewModel
from ui.views.view_types import ViewId


class ViewNavigation(Protocol):
    """Catalog and lifecycle operations needed by the main menu."""

    def menu_options(
            self,
            view_ids: set[ViewId],
    ) -> tuple[tuple[ViewId, str, bool], ...]: ...

    def set_enabled(self, view_id: ViewId, enabled: bool): ...


class MainMenuViewModel(ViewModel):
    """Application commands exposed by the main menu bar."""

    VIEW_MENU_IDS = {
        ViewId.TIME_CONTROL,
        ViewId.DATA,
        ViewId.MAP_WEATHER_CONTROL,
    }

    def __init__(
            self,
            view_navigation: ViewNavigation,
            state: ViewState = view_state,
    ):
        super().__init__()
        self._state = state
        self._view_navigation = view_navigation

    @property
    def view_options(self):
        return self._view_navigation.menu_options(self.VIEW_MENU_IDS)

    def view_enabled(self, view_id) -> bool:
        return self._state.enabled_views.get(view_id, False)

    def set_view_enabled(self, view_id, enabled: bool):
        self._view_navigation.set_enabled(view_id, enabled)

    def open_view(self, view_id):
        self.set_view_enabled(view_id, True)

    @staticmethod
    def reset_camera():
        render_state.camera_reset = True
        render_state.changed = True
