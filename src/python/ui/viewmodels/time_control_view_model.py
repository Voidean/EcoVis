from datetime import timezone

from model.state.time_state import TimeState, time_state
from ui.view_model import ViewModel
from util.time_util import TIME_FORMAT_DISPLAY


class TimeControlViewModel(ViewModel):
    def __init__(self, state: TimeState = time_state):
        super().__init__()
        self._state = state
        self.input_dt = state.current_time.astimezone(timezone.utc)

    @property
    def paused(self) -> bool:
        return self._state.paused

    @property
    def speed(self) -> float:
        return self._state.speed

    @property
    def current_time(self):
        return self._state.current_time

    @property
    def utc_time_text(self) -> str:
        return self.current_time.astimezone(timezone.utc).strftime(
            TIME_FORMAT_DISPLAY
        )

    @property
    def local_time_text(self) -> str:
        return self.current_time.astimezone().strftime(TIME_FORMAT_DISPLAY)

    def toggle_paused(self):
        self._state.paused = not self._state.paused

    def set_speed(self, speed: float):
        self._state.speed = min(max(float(speed), 0.0), 24.0)

    def apply_input_time(self):
        if self._state.current_time != self.input_dt:
            self._state.current_time = self.input_dt
            self._state.changed = True

    def sync_input_from_current(self):
        self.input_dt = self._state.current_time.astimezone(timezone.utc)
