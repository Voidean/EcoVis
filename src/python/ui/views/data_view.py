"""One dockable data window and its component-level controls.

Runtime creation and cross-window ownership live in ``data_view_group``;
generic ImGui window behavior lives in ``window_view``.
"""

from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, TypeAlias

from imgui_bundle import imgui
from typing_extensions import override

from ui.components.base_component import Component
from ui.components.composite_component import CompositeComponent
from ui.composition import graph_merging as _graph_merging
from ui.composition.component_merging import ComponentMergeRule
from ui.docking.workspace import (
    DockingWorkspace,
    default_docking_workspace,
)
from ui.docking.content_layout import DockPlacement
from ui.components.data_controls_component import (
    DataComponentControls,
    SharedDataControlsComponent,
)
from ui.components.generic_components import GenericComponent
from ui.components.data_export_component import DataExportComponent
from ui.components.user_script_selection import UserScriptSelection
from ui.components.user_script_result import create_result_component
from scripts.user_script import UserScript
from ui.views.view_types import ViewMetadata
from ui.viewmodels.dock_window_view_model import DockWindowViewModel
from ui.views.docking_renderer import DockingRenderer
from ui.views.window_view import WindowView

if TYPE_CHECKING:
    from ui.views.data_view_group import DataViewGroup


ComponentFactory: TypeAlias = Callable[[], Component]


class DataView(WindowView[DockWindowViewModel[Component]]):
    """A dockable window with automatic controls for data components."""

    def __init__(
            self,
            metadata: ViewMetadata,
            content: Iterable[Component],
            *,
            group: "DataViewGroup",
            workspace: DockingWorkspace[Component] = default_docking_workspace,
            allow_empty: bool = False,
            instance_number: int = 1,
            max_columns: int = 2,
            component_options: Iterable[
                tuple[str, ComponentFactory]
            ] = (),
    ):
        self._group = group
        self.instance_number = instance_number
        self._component_controllers: dict[
            Component,
            DataComponentControls,
        ] = {}
        components = list(content)
        if any(not isinstance(component, Component) for component in components):
            raise TypeError("DataView content must contain Components")
        if not components and not allow_empty:
            components = [GenericComponent()]

        view_model = DockWindowViewModel(
            metadata.id,
            f"{metadata.title} {instance_number}",
            components,
            manager=group,
            workspace=workspace,
            max_columns=max_columns,
        )
        super().__init__(
            metadata,
            view_model=view_model,
            preferred_size=self._preferred_size_for(components),
            save_size=False,
        )
        self._docking_renderer = DockingRenderer(
            view_model,
            self,
            tuple(component_options),
        )
        self._shared_controls = SharedDataControlsComponent()
        self._rendered_active_component = view_model.active_component
        self._user_script_selection = UserScriptSelection(
            component_provider=lambda: self.contents,
            on_result=self._add_user_script_result,
        )
        self._data_export = DataExportComponent(
            component_provider=lambda: self.contents,
        )

    @property
    def contents(self) -> tuple[Component, ...]:
        return self.view_model.components

    @property
    def display_name(self) -> str:
        return self.view_model.display_name

    @property
    def layout_rows(self) -> tuple[tuple[Component, ...], ...]:
        return self.view_model.layout_rows

    def restore_layout(self, rows: Iterable[Iterable[Component]]):
        self.view_model.restore_layout(rows)

    @property
    def shared_control_state(self) -> dict[str, bool]:
        state = self._shared_controls.view_model
        return {
            "share_geo_pos": state.share_geo_pos,
            "share_time": state.share_time,
        }

    def restore_shared_control_state(self, state: dict):
        self._shared_controls.bind(self.contents)
        view_model = self._shared_controls.view_model
        view_model.set_geo_sharing(state.get("share_geo_pos", False))
        view_model.set_time_sharing(state.get("share_time", False))

    def move_component_here(self, component: Component) -> bool:
        return self.view_model.move_here(component)

    @override
    def render_content(self):
        self.sync_dock_state()
        if self._shared_controls.render(self.contents):
            imgui.separator()
        self._user_script_selection.render()
        if self._user_script_selection.enabled:
            imgui.separator()
        self._data_export.render()
        if self._data_export.enabled:
            imgui.separator()
        self._docking_renderer.render()
        self.sync_dock_state()

    def render_component(self, component: Component):
        controller = self._component_controllers.get(component)
        if controller is None:
            controller = DataComponentControls(component)
            self._component_controllers[component] = controller
        controller.render()
        component.render()

    def add_component(self, factory: ComponentFactory) -> Component:
        component = factory()
        if not isinstance(component, Component):
            raise TypeError("A component factory must return a Component")
        try:
            if not self.view_model.add(component):
                raise ValueError("The component could not be added")
        except Exception:
            if self.view_model.workspace.owner_of(component) is None:
                component.destroy()
            raise
        return component

    def remove_component(self, component: Component):
        try:
            self.view_model.remove(component)
        finally:
            if self.view_model.workspace.owner_of(component) is None:
                component.destroy()

    def merge_components(
            self,
            rule: ComponentMergeRule,
            candidates: Sequence[Component],
    ) -> Component:
        candidates = tuple(candidates)
        if len(candidates) < rule.minimum_components:
            raise ValueError(
                f"{rule.label} requires at least {rule.minimum_components} components"
            )
        if len({component.instance_id for component in candidates}) != len(candidates):
            raise ValueError("A component can only occur once in a merge")
        if any(not self.view_model.contains(component) for component in candidates):
            raise ValueError("All merged components must belong to this window")
        if any(not rule.accepts(component) for component in candidates):
            raise ValueError("A component is not accepted by this merge rule")

        merged = rule.merge(candidates)
        if not isinstance(merged, Component):
            raise TypeError("A merge rule must return a Component")
        if self.view_model.workspace.owner_of(merged) is not None:
            raise ValueError("A merge rule must return a new Component")
        try:
            self.view_model.replace_many(candidates, merged)
        except Exception:
            if self.view_model.workspace.owner_of(merged) is None:
                if isinstance(merged, CompositeComponent):
                    merged.release_components()
                merged.destroy()
            raise
        return merged

    def split_component(
            self,
            composite: CompositeComponent,
    ) -> list[Component]:
        if not self.view_model.contains(composite):
            raise ValueError("The merged component does not belong to this window")
        children = list(composite.components)
        if len({component.instance_id for component in children}) != len(children):
            raise ValueError("A child component can only occur once")
        if any(
                self.view_model.workspace.owner_of(component) is not None
                for component in children
        ):
            raise ValueError("A child component already has a dock owner")

        released = composite.release_components()
        if (
                len(released) != len(children)
                or any(actual is not expected for actual, expected in zip(released, children))
        ):
            raise RuntimeError("The composite changed while it was being separated")
        try:
            self.view_model.replace_one(composite, children)
        finally:
            if self.view_model.workspace.owner_of(composite) is None:
                composite.destroy()
        return children

    def _add_user_script_result(self, script: UserScript, result):
        component = create_result_component(script, result)
        target = self.contents[0] if self.contents else None
        placement = (
            DockPlacement.ABOVE
            if target is not None
            else DockPlacement.BOTTOM
        )
        try:
            if not self.view_model.add(
                    component,
                    target=target,
                    placement=placement,
            ):
                raise RuntimeError("Could not add the user-script result")
        except Exception:
            if self.view_model.workspace.owner_of(component) is None:
                component.destroy()
            raise

    def hide_content(self):
        self.sync_dock_state()
        self._shared_controls.hide()
        self._user_script_selection.hide()
        self._data_export.hide()
        for controller in self._component_controllers.values():
            controller.hide()
        for component in self.contents:
            component.hide()

    @override
    def destroy(self):
        if self._retired:
            return
        self._group.close_view(self)

    def label(self):
        return f"{self.metadata.title}##data_window_{self.view_model.instance_id}"

    def hide_component_controls(self, component: Component):
        controller = self._component_controllers.get(component)
        if controller:
            controller.hide()

    def destroy_content(self):
        self._release_contents(destroy_components=True)

    def retire(self, *, destroy_components: bool):
        """Remove this view from service and release its owned resources."""
        if self._retired:
            return
        self._release_contents(destroy_components=destroy_components)
        self._finish_destroy()

    def _release_contents(self, *, destroy_components: bool):
        components = self.contents
        self._docking_renderer.destroy()
        self._destroy_component_controllers()
        self._user_script_selection.destroy()
        self._data_export.destroy()
        self.view_model.release()
        if destroy_components:
            for component in components:
                component.destroy()

    def _destroy_component_controllers(self):
        self._shared_controls.destroy(self.contents)
        for controller in self._component_controllers.values():
            controller.destroy()
        self._component_controllers.clear()

    def sync_dock_state(self):
        current = set(self.contents)
        for component in tuple(self._component_controllers):
            if component not in current:
                self._shared_controls.release(component)
                self._component_controllers.pop(component).destroy()

        active = self.view_model.active_component
        if self._rendered_active_component is not active:
            if self._rendered_active_component is not None:
                self.hide_component_controls(self._rendered_active_component)
            self._rendered_active_component = active

        for component in current:
            if component.preferred_size is not None:
                self.preferred_size = (
                    max(self.preferred_size[0], component.preferred_size[0]),
                    max(self.preferred_size[1], component.preferred_size[1]),
                )

    @staticmethod
    def _preferred_size_for(
            components: Iterable[Component],
    ) -> tuple[int, int]:
        sizes = [
            component.preferred_size
            for component in components
            if component.preferred_size is not None
        ]
        return (
            (max(size[0] for size in sizes), max(size[1] for size in sizes))
            if sizes
            else (700, 625)
        )
