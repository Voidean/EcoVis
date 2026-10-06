_checkpoint_handler = lambda: None


def set_checkpoint_handler(handler):
    global _checkpoint_handler
    _checkpoint_handler = handler


def clear_checkpoint_handler():
    global _checkpoint_handler
    _checkpoint_handler = lambda: None


def checkpoint():
    _checkpoint_handler()
