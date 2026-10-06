from datetime import datetime, timezone
from typing import override

from imgui_bundle import imgui

from ui.components.base_component import Component


class DatePickerComponent(Component):
    """Date-range editor composed against another component's ViewModel."""

    def __init__(self, state):
        super().__init__(getattr(state, "view_model", state))

    def _normalize_utc(self, attribute: str) -> datetime:
        value = getattr(self.state, attribute)
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        if normalized != value:
            setattr(self.state, attribute, normalized)
        return normalized

    @override
    def render(self) -> bool:
        changed = False
        if self.state and not self.state.render_datepicker: return changed
        self._normalize_utc("start_time")
        self._normalize_utc("end_time")
        imgui.text("Start (UTC):")
        changed |= self.datepicker("start_time", precision=self.state.date_precision, max_date=self.state.end_time)
        if self.state.end_time:
            imgui.text("End (UTC):")
            changed |= self.datepicker("end_time", precision=self.state.date_precision, min_date=self.state.start_time)
        return changed
