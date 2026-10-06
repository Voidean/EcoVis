import re
from abc import ABC, abstractmethod
from itertools import count
from typing import Generic, TypeVar

from ui.imgui_controls import ImGuiControls
from ui.view_model import ViewModel


_component_instance_ids = count(1)
ViewModelT = TypeVar("ViewModelT", bound=ViewModel)


class Component(ImGuiControls, ABC):
    """Reusable ImGui fragment, analogous to a Compose ``@Composable``.

    Components never own an ImGui window. A :class:`ui.views.base_view.View`
    or another component provides that rendering context.
    """

    instance_id: int

    def __init__(self, state=None):
        super().__init__(state)
        if not hasattr(self, "instance_id"):
            self.instance_id = next(_component_instance_ids)
        self.__dict__["changed"] = False
        self.preferred_size = None

    @abstractmethod
    def render(self):
        pass

    def update(self, **kwargs):
        pass

    def hide(self):
        pass

    @property
    def display_name(self) -> str:
        """Human-readable name used by generic component hosts."""
        name = type(self).__name__
        for suffix in ("WindowComponent", "Component"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


class ViewModelComponent(Component, Generic[ViewModelT], ABC):
    """A stateful component bound explicitly to a ViewModel.

    Rendering-only child components can instead inherit :class:`Component`
    directly and pass whatever local state they need to its constructor.
    """

    def __init__(self, view_model: ViewModelT):
        # Call Component directly. Graph components also use capability
        # mixins, so cooperative initialization could bind state more than once.
        Component.__init__(self, view_model)
        self.view_model = view_model
        self._view_model_destroyed = False

    @property
    def changed(self) -> bool:
        view_model = self.__dict__.get("view_model")
        if view_model is not None:
            return view_model.changed
        return self.__dict__.get("changed", False)

    @changed.setter
    def changed(self, value: bool):
        view_model = self.__dict__.get("view_model")
        if view_model is not None:
            view_model.changed = value
        else:
            self.__dict__["changed"] = value

    def __getattr__(self, name):
        view_model = self.__dict__.get("view_model")
        if view_model is not None:
            try:
                return getattr(view_model, name)
            except AttributeError:
                pass
        raise AttributeError(
            f"{type(self).__name__!s} has no attribute {name!r}"
        )

    def update(self, **kwargs):
        self.view_model.update(**kwargs)

    def prepare_render(self):
        """Advance the bound state before submitting ImGui items."""
        self.view_model.tick()

    def hide(self):
        self.view_model.hide()

    def destroy(self):
        if not self._view_model_destroyed:
            self.view_model.destroy()
            self._view_model_destroyed = True
        Component.destroy(self)
