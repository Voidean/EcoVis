class DebugState:
    def __init__(self):
        self.changed = False
        self.quad_tree = None
        self.display_tile_boundaries = False


debug_state: DebugState = DebugState()
