from datetime import datetime
from typing import Any, Iterable

from model.geo_pos import GeoPos
from ui.view_model import ViewModel


class SharedDateRangeViewModel(ViewModel):
    def __init__(
            self,
            start_time: datetime,
            end_time: datetime,
            date_precision: list[str],
    ):
        super().__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.date_precision = date_precision
        self.render_datepicker = True


class SharedDataControlsViewModel(ViewModel):
    """Coordinates optional window-wide position and time edits."""

    def __init__(self):
        super().__init__()
        self.share_geo_pos = False
        self.share_time = False
        self.geo_pos: GeoPos | None = None
        self.date_state: SharedDateRangeViewModel | None = None
        self._geo_states: tuple[Any, ...] = ()
        self._date_states: tuple[Any, ...] = ()
        self._shared_geo_ids: set[int] = set()
        self._shared_date_ids: set[int] = set()

    def bind(
            self,
            geo_states: Iterable,
            date_states: Iterable,
    ):
        geo_states = tuple(geo_states)
        date_states = tuple(date_states)
        self._geo_states = geo_states
        self._date_states = date_states

        if len(geo_states) <= 1:
            self.set_geo_sharing(False)
        if len(date_states) <= 1:
            self.set_time_sharing(False)

        self._apply_visibility()
        self._update_new_shared_components()

    def set_geo_sharing(self, enabled: bool):
        enabled = bool(enabled and len(self._geo_states) > 1)
        if self.share_geo_pos == enabled:
            return
        self.share_geo_pos = enabled
        if enabled:
            source = next(
                (
                    state.geo_pos
                    for state in self._geo_states
                    if state.geo_pos is not None
                ),
                None,
            )
            if source is not None:
                self.update_geo_pos(source)
            self._shared_geo_ids = {
                id(state) for state in self._geo_states
            }
        else:
            self._shared_geo_ids.clear()
        self._apply_visibility()

    def set_time_sharing(self, enabled: bool):
        enabled = bool(enabled and len(self._date_states) > 1)
        if self.share_time == enabled:
            return
        self.share_time = enabled
        if enabled:
            source = self._date_states[0]
            self.date_state = SharedDateRangeViewModel(
                source.start_time,
                source.end_time,
                self._combined_date_precision(self._date_states),
            )
            self.apply_time()
            self._shared_date_ids = {
                id(state) for state in self._date_states
            }
        else:
            if self.date_state is not None:
                self.date_state.destroy()
            self.date_state = None
            self._shared_date_ids.clear()
        self._apply_visibility()

    def update_geo_pos(self, geo_pos: GeoPos):
        self.geo_pos = geo_pos
        for state in self._geo_states:
            state.update(geo_pos=geo_pos)

    def apply_time(self, states: Iterable | None = None):
        if self.date_state is None:
            return
        targets = (
            self._date_states
            if states is None
            else tuple(states)
        )
        for state in targets:
            state.update(
                start_time=self.date_state.start_time,
                end_time=self.date_state.end_time,
            )

    def release(self, states: Iterable):
        released = tuple(states)
        released_ids = {id(state) for state in released}
        self._geo_states = tuple(
            state for state in self._geo_states
            if id(state) not in released_ids
        )
        self._date_states = tuple(
            state for state in self._date_states
            if id(state) not in released_ids
        )
        for state in released:
            self._shared_geo_ids.discard(id(state))
            self._shared_date_ids.discard(id(state))
            if hasattr(state, "render_individual_geo_pos_selector"):
                state.render_individual_geo_pos_selector = True
            if hasattr(state, "render_individual_datepicker"):
                state.render_individual_datepicker = True

    def _apply_visibility(self):
        for state in self._geo_states:
            state.render_individual_geo_pos_selector = not self.share_geo_pos
        for state in self._date_states:
            state.render_individual_datepicker = not self.share_time

    def _update_new_shared_components(self):
        if self.share_geo_pos and self.geo_pos is not None:
            for state in self._geo_states:
                if id(state) not in self._shared_geo_ids:
                    state.update(geo_pos=self.geo_pos)
        if self.share_geo_pos:
            self._shared_geo_ids = {
                id(state) for state in self._geo_states
            }

        if self.share_time and self.date_state is not None:
            self.apply_time(
                state
                for state in self._date_states
                if id(state) not in self._shared_date_ids
            )
            self._shared_date_ids = {
                id(state) for state in self._date_states
            }

    @staticmethod
    def _combined_date_precision(states: tuple) -> list[str]:
        supported = {
            unit
            for state in states
            for unit in state.date_precision
        }
        return [
            unit for unit in ("Year", "Month", "Day", "Hour", "Minute")
            if unit in supported
        ]

    def destroy(self):
        if self.destroyed:
            return
        for state in (*self._geo_states, *self._date_states):
            if hasattr(state, "render_individual_geo_pos_selector"):
                state.render_individual_geo_pos_selector = True
            if hasattr(state, "render_individual_datepicker"):
                state.render_individual_datepicker = True
        if self.date_state is not None:
            self.date_state.destroy()
            self.date_state = None
        self._geo_states = ()
        self._date_states = ()
        super().destroy()
