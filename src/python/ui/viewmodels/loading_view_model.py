import time

from ui.view_model import ViewModel


class LoadingViewModel(ViewModel):
    """Progress state and frame throttling for the independent splash view."""

    def __init__(self):
        super().__init__()
        self.progress = 0.0
        self.text = "Loading..."
        self._last_render = 0.0

    @property
    def progress_percent(self) -> int:
        return int(self.progress * 100)

    def update(self, progress=None, text=None, **_):
        if progress is not None:
            self.progress = min(max(float(progress), 0.0), 1.0)
        if text is not None:
            self.text = text

    def should_render(self, force: bool = False) -> bool:
        now = time.perf_counter()
        if not force and now - self._last_render < 1.0 / 30.0:
            return False
        self._last_render = now
        return True
