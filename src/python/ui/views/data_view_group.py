"""Runtime window management for one dockable data feature.

Typical usage is one registration::

    view_registry.register(ViewId.WEATHER, DataViewGroup(
        ViewMetadata(ViewId.WEATHER, "Weather"),
        WeatherGraphComponent,
    ))

The group creates windows, handles component transfers, and owns cleanup.
"""

from collections.abc import Iterable, Iterator

from ui.components.base_component import Component
from ui.components.generic_components import GenericComponent
from ui.docking.workspace import (
    DockingWorkspace,
    default_docking_workspace,
)
from ui.viewmodels.dock_window_view_model import DockWindowViewModel
from ui.views.data_view import ComponentFactory, DataView
from ui.views.view_types import ViewMetadata


class DataViewGroup:
    """Create, close, restore, and transfer between data windows."""

    def __init__(
            self,
            metadata: ViewMetadata,
            *component_factories: ComponentFactory,
            view_type: type[DataView] = DataView,
            workspace: DockingWorkspace[Component] = default_docking_workspace,
            max_columns: int = 2,
            component_options: Iterable[
                tuple[str, ComponentFactory]
            ] = (),
    ):
        self.metadata = metadata
        self.component_factories = tuple(
            component_factories or (GenericComponent,)
        )
        for factory in self.component_factories:
            if not callable(factory):
                raise TypeError("DataViewGroup expects component factories")
        if max_columns < 1:
            raise ValueError("A data window needs at least one column")
        self.view_type = view_type
        self.workspace = workspace
        self.max_columns = max_columns
        self.component_options = tuple(component_options)
        self._views: list[DataView] = []
        self._next_instance_number = 1
        self.add_view()

    @property
    def views(self) -> tuple[DataView, ...]:
        return tuple(self._views)

    def __iter__(self) -> Iterator[DataView]:
        return iter(self.views)

    def __len__(self) -> int:
        return len(self._views)

    @property
    def is_retired(self) -> bool:
        return False

    def render(self, dt):
        for view in self.views:
            view.render(dt)

    def destroy(self):
        for view in tuple(self._views):
            self._remove_view(view, destroy_components=True)

    def add_view(self) -> DataView:
        return self._create_view([], allow_empty=True)

    def restore_views(
            self,
            layouts: Iterable[Iterable[Iterable[Component]]],
    ):
        """Replace runtime views with already recreated component layouts."""
        restored = [[list(row) for row in rows] for rows in layouts]
        if not restored:
            return
        if any(
                not rows
                or any(not row or len(row) > self.max_columns for row in rows)
                for rows in restored
        ):
            raise ValueError("Invalid restored Data window layout")
        for view in tuple(self._views):
            self._remove_view(view, destroy_components=True)
        self._next_instance_number = 1
        for rows in restored:
            components = [component for row in rows for component in row]
            view = self._create_view(components)
            view.restore_layout(rows)

    def move_to_new_window(self, component: Component) -> DataView:
        if self.workspace.owner_of(component) is None:
            raise ValueError("The component is not part of this workspace")
        destination = self._create_view([], allow_empty=True)
        if not destination.move_component_here(component):
            self._remove_view(destination, destroy_components=False)
            raise ValueError("The component could not be moved to a new window")
        return destination

    def close_view(self, view: DataView):
        self._require_view(view)
        if len(self._views) == 1:
            view.hide()
            return
        self._remove_view(view, destroy_components=True)

    def handle_empty_window(
            self,
            window: DockWindowViewModel[Component],
    ):
        view = self._view_for(window)
        if len(self._views) == 1:
            return
        self._remove_view(view, destroy_components=False)

    def dock_state_changed(
            self,
            window: DockWindowViewModel[Component],
    ):
        self._view_for(window).sync_dock_state()

    def _create_view(
            self,
            components: Iterable[Component],
            *,
            allow_empty: bool = False,
    ) -> DataView:
        number = self._next_instance_number
        self._next_instance_number += 1
        view = self.view_type(
            self.metadata,
            list(components),
            group=self,
            workspace=self.workspace,
            allow_empty=allow_empty,
            instance_number=number,
            max_columns=self.max_columns,
            component_options=self.component_options,
        )
        self._views.append(view)
        return view

    def _remove_view(
            self,
            view: DataView,
            *,
            destroy_components: bool,
    ):
        self._require_view(view)
        self._views.remove(view)
        view.retire(destroy_components=destroy_components)

    def _require_view(self, view: DataView):
        if view not in self._views:
            raise ValueError("The data window does not belong to this group")

    def _view_for(
            self,
            window: DockWindowViewModel[Component],
    ) -> DataView:
        view = next(
            (view for view in self._views if view.view_model is window),
            None,
        )
        if view is None:
            raise ValueError("The dock window does not belong to this group")
        return view
