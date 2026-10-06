from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.viewmodels.sync_view_model import (
    SyncViewModel,
    get_current_host_search,
    set_current_host_search,
)


class SyncControlsComponent(Component):
    """Composable controls for a :class:`SyncViewModel`."""

    def __init__(self, view_model: SyncViewModel):
        super().__init__(view_model)
        self.view_model = view_model

    def render(self):
        view_model = self.view_model
        searching = get_current_host_search()
        if searching is None and not view_model.host:
            if imgui.button("Sync another component to this"):
                set_current_host_search(view_model)
        elif searching is view_model:
            if imgui.button("Cancel sync search"):
                set_current_host_search(None)
        elif not view_model.host:
            if imgui.button("Sync to other component"):
                searching.set_sync_host(view_model)
                set_current_host_search(None)
        if view_model.host:
            if imgui.button("Stop Syncing from Host"):
                view_model.desync()
