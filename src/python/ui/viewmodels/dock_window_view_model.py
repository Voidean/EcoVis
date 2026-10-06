"""View model for one dockable content window."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import count
from typing import Generic, Protocol, TypeVar

from ui.docking.content_layout import ContentLayout, DockPlacement
from ui.docking.dock_item import DockItem
from ui.docking.workspace import DockingWorkspace
from ui.viewmodels.view_lifecycle_view_model import ViewLifecycleViewModel


DockItemT = TypeVar("DockItemT", bound=DockItem)
_dock_window_ids = count(1)


class DockWindowManager(Protocol[DockItemT]):
    """Window lifecycle operations required by the docking view model."""

    def handle_empty_window(
            self,
            window: DockWindowViewModel[DockItemT],
    ): ...

    def move_to_new_window(self, component: DockItemT) -> object | None: ...

    def dock_state_changed(
            self,
            window: DockWindowViewModel[DockItemT],
    ): ...


class DockWindowViewModel(ViewLifecycleViewModel, Generic[DockItemT]):
    """Expose window-local docking state and commands without View imports.

    Docked content is opaque and only required to have a runtime ID. Creating,
    rendering, merging, and destroying concrete UI components remain View
    responsibilities. Cross-window ownership is delegated to the workspace.
    """

    def __init__(
            self,
            view_id,
            display_name: str,
            components: Iterable[DockItemT],
            *,
            manager: DockWindowManager[DockItemT],
            workspace: DockingWorkspace[DockItemT],
            max_columns: int = 2,
    ):
        super().__init__(view_id)
        self.instance_id = next(_dock_window_ids)
        self.display_name = display_name
        self.layout = ContentLayout[DockItemT](
            components,
            max_columns=max_columns,
        )
        self.workspace = workspace
        self._manager = manager
        self._active_component = self.components[0] if self.components else None
        self._released = False
        self.workspace.register_window(self)

    @property
    def components(self) -> tuple[DockItemT, ...]:
        return self.layout.items

    @property
    def layout_rows(self) -> tuple[tuple[DockItemT, ...], ...]:
        return self.layout.rows

    @property
    def active_component(self) -> DockItemT | None:
        if self._active_component in self.layout:
            return self._active_component
        return self.components[0] if self.components else None

    @property
    def is_available_for_docking(self) -> bool:
        return not self._released and self.visible

    def contains(self, component: DockItemT) -> bool:
        return component in self.layout

    def can_place(
            self,
            component: DockItemT,
            *,
            target: DockItemT | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        return self.layout.can_place(
            component,
            target=target,
            placement=placement,
        )

    def add(
            self,
            component: DockItemT,
            *,
            target: DockItemT | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        if self.workspace.owner_of(component) is self:
            self.activate(component)
            return False
        return self.workspace.move(
            component,
            self,
            target=target,
            placement=placement,
        )

    def move_here(
            self,
            component: DockItemT,
            *,
            target: DockItemT | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        return self.workspace.move(
            component,
            self,
            target=target,
            placement=placement,
        )

    def remove(self, component: DockItemT):
        self.workspace.remove(component, self)

    def replace_many(
            self,
            components: Sequence[DockItemT],
            replacement: DockItemT,
    ):
        self.workspace.replace_many(self, components, replacement)

    def replace_one(
            self,
            component: DockItemT,
            replacements: Sequence[DockItemT],
    ):
        self.workspace.replace_one(self, component, replacements)

    def activate(self, component: DockItemT | None):
        if component is not None and component not in self.layout:
            raise ValueError("The active component must belong to this window")
        self._active_component = component

    def component_released(self, component: DockItemT):
        if self._active_component is component:
            self._active_component = self.components[0] if self.components else None

    def reset_layout(self):
        self.layout.stack()

    def restore_layout(self, rows: Iterable[Iterable[DockItemT]]):
        rows = tuple(tuple(row) for row in rows)
        restored = tuple(component for row in rows for component in row)
        if (
                len(restored) != len(self.components)
                or {id(component) for component in restored}
                != {id(component) for component in self.components}
        ):
            raise ValueError("A restored layout must contain the current components")
        self.layout.restore(rows)

    def move_to_new_window(self, component: DockItemT) -> bool:
        if not self.contains(component):
            return False
        return bool(self._manager.move_to_new_window(component))

    def handle_empty(self):
        self._manager.handle_empty_window(self)

    def notify_state_changed(self):
        self._manager.dock_state_changed(self)

    def release(self):
        if self._released:
            return
        self.workspace.unregister_window(self)
        self._released = True

    def destroy(self):
        self.release()
        super().destroy()
