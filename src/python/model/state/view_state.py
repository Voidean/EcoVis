from __future__ import annotations

from ui.views.view_types import ViewId
from util.config import config, ConfigChanges


class ViewState:
    def __init__(self):
        self.enabled_views = {
            ViewId.MAIN_MENU_BAR: True,
            ViewId.TIME_CONTROL: True,
            ViewId.DEBUG: False,
            ViewId.CONFIG: False,
        }
        known_ids = {
            ViewId.DATA,
            ViewId.MAP_WEATHER_CONTROL,
        }
        for key, value in config.get("enabled_windows").__dict__.items():
            if key in self.enabled_views or key in known_ids:
                self.enabled_views[key] = value

    def save_enabled_views(self):
        changes = ConfigChanges()
        for key, value in self.enabled_views.items():
            changes.set(f"enabled_windows.{key}", value)
        config.save(changes.values)
view_state = ViewState()
