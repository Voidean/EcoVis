"""Shared ImGui window shell for component-hosting views."""

from abc import abstractmethod
from typing import Generic, TypeVar, cast

from imgui_bundle import imgui

from ui.viewmodels.view_lifecycle_view_model import ViewLifecycleViewModel
from ui.views.base_view import View
from ui.views.view_types import ViewMetadata


LifecycleViewModelT = TypeVar(
    "LifecycleViewModelT",
    bound=ViewLifecycleViewModel,
)


class WindowView(View[LifecycleViewModelT], Generic[LifecycleViewModelT]):
    """Own an ImGui window while subclasses provide only its contents.

    This class centralizes window geometry, close behavior, and visibility.
    It deliberately knows nothing about components or docking.
    """

    def __init__(
            self,
            metadata: ViewMetadata,
            *,
            view_model: LifecycleViewModelT | None = None,
            preferred_size: tuple[int, int] = (700, 625),
            destroy_on_close: bool = True,
            save_size: bool = True,
    ):
        resolved_view_model = (
            view_model
            if view_model is not None
            else cast(LifecycleViewModelT, ViewLifecycleViewModel(metadata.id))
        )
        super().__init__(metadata, resolved_view_model)
        self.preferred_size = preferred_size
        self.restored_position: tuple[float, float] | None = None
        self.restored_size: tuple[float, float] | None = None
        self.destroy_on_close = destroy_on_close
        self.save_size = save_size
        self._retired = False

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def lifecycle(self) -> LifecycleViewModelT:
        return self.view_model

    def render(self, dt):
        if self._retired:
            return
        self.prepare_render()
        self._prepare_window_geometry()

        expanded, is_opened = imgui.begin(
            self.label(),
            p_open=True,
            flags=(
                imgui.WindowFlags_.no_saved_settings
                if not self.save_size
                else 0
            ),
        )
        if not is_opened:
            if self.destroy_on_close:
                self.destroy()
            else:
                self.hide()
            imgui.end()
            return

        if expanded:
            self.render_content()
        self._capture_window_geometry(capture_size=expanded)
        imgui.end()

    def label(self) -> str:
        return self.metadata.title

    @abstractmethod
    def render_content(self):
        """Render inside the active ImGui window scope."""

    @abstractmethod
    def hide_content(self):
        """Notify hosted content that it is no longer visible."""

    @abstractmethod
    def destroy_content(self):
        """Release resources owned by the concrete window contents."""

    def hide(self):
        self.lifecycle.hide()
        self.hide_content()

    def destroy(self):
        if self._retired:
            return
        self.lifecycle.hide()
        self.destroy_content()
        self._finish_destroy()

    def _finish_destroy(self):
        """Retire the shell after a subclass has released its contents."""
        if self._retired:
            return
        super().destroy()
        self._retired = True

    def _prepare_window_geometry(self):
        if self.restored_position is not None:
            imgui.set_next_window_pos(
                imgui.ImVec2(*self.restored_position),
                cond=imgui.Cond_.first_use_ever,
            )
        imgui.set_next_window_size(
            imgui.ImVec2(*(self.restored_size or self.preferred_size)),
            cond=imgui.Cond_.first_use_ever,
        )

    def _capture_window_geometry(self, *, capture_size: bool = True):
        position = imgui.get_window_pos()
        self.restored_position = (position.x, position.y)
        if capture_size:
            size = imgui.get_window_size()
            self.restored_size = (size.x, size.y)
