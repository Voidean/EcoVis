from ui.view_model import ViewModel


class FpsViewModel(ViewModel):
    def __init__(self):
        super().__init__()
        self.delta_time = 0.0
        self.fps = float("inf")

    def set_delta_time(self, delta_time: float):
        self.delta_time = delta_time

    def tick(self):
        self.fps = (
            1.0 / self.delta_time
            if self.delta_time > 0
            else float("inf")
        )
