"""UI-independent coordination of components between dockable windows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from ui.docking.dock_item import DockItem
from ui.docking.content_layout import DockPlacement

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ui.viewmodels.dock_window_view_model import DockWindowViewModel


DockItemT = TypeVar("DockItemT", bound=DockItem)


class DockingWorkspace(Generic[DockItemT]):
    """Own the cross-window component index and apply atomic transfers.

    Window-local state and commands live in :class:`DockWindowViewModel`.
    This service only handles invariants which span multiple windows.  It has
    deliberately no ImGui or concrete View dependency.
    """

    def __init__(self):
        self._windows: list[DockWindowViewModel[DockItemT]] = []
        self._locations: dict[
            int,
            tuple[DockItemT, DockWindowViewModel[DockItemT]],
        ] = {}
        self._dragged_component_id: int | None = None
        self._drop_was_accepted = False
        self._host_was_hovered = False

    @property
    def windows(self) -> tuple[DockWindowViewModel[DockItemT], ...]:
        return tuple(self._windows)

    def register_window(self, window: DockWindowViewModel[DockItemT]):
        if window in self._windows:
            return
        registered: list[DockItemT] = []
        try:
            for component in window.components:
                self._register_component(component, window)
                registered.append(component)
        except Exception:
            for component in registered:
                self._unregister_component(component, window)
            raise
        self._windows.append(window)

    def unregister_window(
            self,
            window: DockWindowViewModel[DockItemT],
    ):
        if window not in self._windows:
            return
        components = window.components
        for component in components:
            self._unregister_component(component, window)
        window.layout.restore(())
        window.activate(None)
        self._windows.remove(window)

    def available_destinations(
            self,
            source: DockWindowViewModel[DockItemT],
    ) -> tuple[DockWindowViewModel[DockItemT], ...]:
        return tuple(
            window
            for window in self._windows
            if window is not source and window.is_available_for_docking
        )

    def resolve_component(self, component_id: int) -> DockItemT | None:
        location = self._locations.get(component_id)
        return location[0] if location is not None else None

    def owner_of(
            self,
            component: DockItemT,
    ) -> DockWindowViewModel[DockItemT] | None:
        location = self._locations.get(component.instance_id)
        if location is None or location[0] is not component:
            return None
        return location[1]

    def move(
            self,
            component: DockItemT,
            destination: DockWindowViewModel[DockItemT],
            *,
            target: DockItemT | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        """Add or move a component while preserving single ownership."""
        if destination not in self._windows:
            raise ValueError("The destination is not part of this workspace")

        source = self.owner_of(component)
        if source is destination:
            moved = destination.layout.move(
                component,
                target=target,
                placement=placement,
            )
            if moved:
                destination.activate(component)
                destination.notify_state_changed()
            return moved

        if not destination.layout.can_place(
                component,
                target=target,
                placement=placement,
        ):
            return False

        if source is None:
            destination.layout.add(
                component,
                target=target,
                placement=placement,
            )
            self._register_component(component, destination)
            destination.activate(component)
            destination.notify_state_changed()
            return True

        source_rows = source.layout.rows
        destination_rows = destination.layout.rows
        try:
            source.layout.remove(component)
            destination.layout.add(
                component,
                target=target,
                placement=placement,
            )
        except Exception:
            source.layout.restore(source_rows)
            destination.layout.restore(destination_rows)
            raise

        self._locations[component.instance_id] = (component, destination)
        source.component_released(component)
        destination.activate(component)
        source.notify_state_changed()
        destination.notify_state_changed()
        if not source.components:
            source.handle_empty()
        return True

    def remove(
            self,
            component: DockItemT,
            window: DockWindowViewModel[DockItemT],
    ):
        if self.owner_of(component) is not window:
            raise ValueError("The component does not belong to this window")
        window.layout.remove(component)
        self._unregister_component(component, window)
        window.component_released(component)
        window.notify_state_changed()
        if not window.components:
            window.handle_empty()

    def replace_many(
            self,
            window: DockWindowViewModel[DockItemT],
            components: Sequence[DockItemT],
            replacement: DockItemT,
    ):
        """Replace registered components with one merged component."""
        components = tuple(components)
        self._require_unique_ids(components)
        self._require_owner(window, components)
        self._require_unowned((replacement,))
        window.layout.replace_many(components, replacement)
        for component in components:
            self._unregister_component(component, window)
        self._register_component(replacement, window)
        window.activate(replacement)
        window.notify_state_changed()

    def replace_one(
            self,
            window: DockWindowViewModel[DockItemT],
            component: DockItemT,
            replacements: Sequence[DockItemT],
    ):
        """Replace one registered composite with its released children."""
        replacements = tuple(replacements)
        self._require_unique_ids(replacements)
        self._require_owner(window, (component,))
        self._require_unowned(replacements)
        window.layout.replace_one(component, replacements)
        self._unregister_component(component, window)
        for replacement in replacements:
            self._register_component(replacement, window)
        window.activate(replacements[0] if replacements else None)
        window.notify_state_changed()
        if not window.components:
            window.handle_empty()

    def start_frame(self):
        """Reset drag observations immediately after ``imgui.new_frame()``."""
        self._drop_was_accepted = False
        self._host_was_hovered = False

    def note_drag(self, component_id: int):
        self._dragged_component_id = component_id

    def note_host_hovered(self):
        self._host_was_hovered = True

    def note_drop_accepted(self):
        self._drop_was_accepted = True

    def finish_frame(
            self,
            *,
            mouse_released: bool,
            drag_payload_active: bool = True,
    ) -> bool:
        """Create a window for a component released outside every host."""
        if not drag_payload_active and not mouse_released:
            self._dragged_component_id = None
            return False
        if not mouse_released or self._dragged_component_id is None:
            return False

        component_id = self._dragged_component_id
        self._dragged_component_id = None
        if self._drop_was_accepted or self._host_was_hovered:
            return False
        component = self.resolve_component(component_id)
        if component is None:
            return False
        source = self.owner_of(component)
        return source.move_to_new_window(component) if source is not None else False

    def _register_component(
            self,
            component: DockItemT,
            window: DockWindowViewModel[DockItemT],
    ):
        existing = self._locations.get(component.instance_id)
        if existing is not None and existing != (component, window):
            raise ValueError("The component already belongs to another window")
        self._locations[component.instance_id] = (component, window)

    def _unregister_component(
            self,
            component: DockItemT,
            window: DockWindowViewModel[DockItemT],
    ):
        if self._locations.get(component.instance_id) == (component, window):
            del self._locations[component.instance_id]

    def _require_owner(
            self,
            window: DockWindowViewModel[DockItemT],
            components: Sequence[DockItemT],
    ):
        if any(self.owner_of(component) is not window for component in components):
            raise ValueError("A component does not belong to this window")

    def _require_unowned(self, components: Sequence[DockItemT]):
        for component in components:
            existing = self._locations.get(component.instance_id)
            if existing is not None:
                raise ValueError("A replacement component already has an owner")

    @staticmethod
    def _require_unique_ids(components: Sequence[DockItemT]):
        if len({component.instance_id for component in components}) != len(components):
            raise ValueError("A dock item can only occur once")


default_docking_workspace = DockingWorkspace()
