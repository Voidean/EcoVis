from model.state.view_state import ViewState, view_state
from ui.view_model import ViewModel


class ViewLifecycleViewModel(ViewModel):
    """Visibility state shared by a concrete View and the main menu."""

    def __init__(self, view_id, state: ViewState = view_state):
        super().__init__()
        self.view_id = view_id
        self._state = state

    @property
    def visible(self) -> bool:
        return self._state.enabled_views.get(self.view_id, False)

    def show(self):
        self._state.enabled_views[self.view_id] = True

    def hide(self):
        self._state.enabled_views[self.view_id] = False
