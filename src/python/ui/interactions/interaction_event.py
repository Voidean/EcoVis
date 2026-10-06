
class InteractionEvent:
    def __init__(self):
        self.consumed = False

    def consume(self):
        """Call this to stop the event from passing to lower-priority handlers."""
        self.consumed = True


class MouseEvent(InteractionEvent):
    def __init__(self, button, mouse_pos, world_pos):
        super().__init__()
        self.button = button
        self.mouse_pos = mouse_pos
        self.world_pos = world_pos


class KeyEvent(InteractionEvent):
    def __init__(self, key):
        super().__init__()
        self.key = key
