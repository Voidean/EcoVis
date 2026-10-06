from ui.view_model import ViewModel


class HelpViewModel(ViewModel):
    def __init__(self):
        super().__init__()
        self.opened = False

    def open(self):
        self.opened = True

    def set_opened(self, opened: bool):
        self.opened = opened
