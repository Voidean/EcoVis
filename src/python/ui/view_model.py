class ViewModel:
    """UI-facing application state without any ImGui rendering calls.

    Immediate-mode views call :meth:`tick` once per rendered frame.  Concrete
    view models can use that hook to collect asynchronous results and process
    state changes without requiring an observable/Flow implementation.
    """

    def __init__(self):
        self.changed = False
        self._destroyed = False

    def update(self, **_):
        """Apply state supplied by another part of the application."""

    def tick(self):
        """Advance application state before rendering, when needed."""

    def commit_edits(self):
        """Commit edits made by reusable controls.

        The default supports legacy state objects which use ``changed`` as a
        dirty flag.  Specialized ViewModels may provide more precise commands.
        """
        self.changed = True

    def hide(self):
        """React to all renderers for this state becoming hidden."""

    def destroy(self):
        """Release resources owned by this view model."""
        self._destroyed = True

    @property
    def destroyed(self) -> bool:
        return self._destroyed
