from model.state.debug_state import DebugState, debug_state
from ui.view_model import ViewModel


class DebugViewModel(ViewModel):
    def __init__(self, state: DebugState = debug_state):
        super().__init__()
        self._state = state
        self.delta_time = 0.0
        self.fps = float("inf")
        self.tile_counts: tuple[tuple[int, int], ...] = ()
        self.total_tiles = 0

    def set_delta_time(self, delta_time: float):
        self.delta_time = delta_time

    def set_value(self, identifier: str, value):
        self._state.__setattr__(identifier, value)
        self._state.changed = True

    def tick(self):
        self.fps = (
            1.0 / self.delta_time
            if self.delta_time > 0
            else float("inf")
        )
        quad_tree = self._state.quad_tree
        if quad_tree is None:
            self.tile_counts = ()
            self.total_tiles = 0
            return

        counts: dict[int, int] = {}
        for leaf in quad_tree.leaves():
            counts[leaf.level] = counts.get(leaf.level, 0) + 1
        self.tile_counts = tuple(sorted(counts.items()))
        self.total_tiles = sum(counts.values())
