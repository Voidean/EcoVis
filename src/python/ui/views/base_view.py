from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from ui.imgui_controls import ImGuiControls
from ui.view_model import ViewModel
from ui.views.view_types import ViewMetadata


ViewModelT = TypeVar("ViewModelT", bound=ViewModel)


class View(ImGuiControls, Generic[ViewModelT], ABC):
    """A complete ImGui window backed by a ViewModel.

    Unlike a Component, a concrete View owns its ``imgui.begin/end`` scope.
    Window flags and close behavior remain the responsibility of that View.
    """

    def __init__(self, metadata: ViewMetadata, view_model: ViewModelT):
        super().__init__(view_model)
        self.metadata = metadata
        self.view_model = view_model

    @abstractmethod
    def render(self, dt):
        raise NotImplementedError

    def prepare_render(self):
        self.view_model.tick()

    @property
    def is_retired(self) -> bool:
        """Whether this view must be recreated before it can be shown."""
        return False

    def destroy(self):
        self.view_model.destroy()
        super().destroy()
