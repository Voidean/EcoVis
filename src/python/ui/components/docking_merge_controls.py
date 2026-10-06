"""Merge and split controls for a dock-window view model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.components.composite_component import CompositeComponent
from ui.composition.component_merging import component_merge_registry
from ui.viewmodels.dock_window_view_model import DockWindowViewModel

if TYPE_CHECKING:
    from ui.views.data_view import DataView


class DockingMergeControls:
    def __init__(
            self,
            view_model: DockWindowViewModel[Component],
            actions: DataView,
    ):
        self.view_model = view_model
        self._actions = actions
        self._selection: dict[str, set[int]] = {}

    def render(self):
        available = component_merge_registry.available_merges(
            self.view_model.components
        )
        for index, (rule, candidates) in enumerate(available):
            if index:
                imgui.same_line()
            popup_id = f"merge_{rule.identifier}_{self.view_model.instance_id}"
            if imgui.button(f"{rule.label}...##{popup_id}"):
                self._selection[rule.identifier] = {
                    component.instance_id for component in candidates
                }
                imgui.open_popup(popup_id)

            if imgui.begin_popup(popup_id):
                self._render_merge_popup(rule, candidates)
                imgui.end_popup()

        active = self.view_model.active_component
        if isinstance(active, CompositeComponent):
            if available:
                imgui.same_line()
            if imgui.button(
                    f"Separate {active.display_name}##split_{active.instance_id}"
            ):
                self._actions.split_component(active)

    def destroy(self):
        self._selection.clear()

    def _render_merge_popup(self, rule, candidates):
        imgui.text("Choose panels to merge:")
        selected = self._selection.setdefault(
            rule.identifier,
            {component.instance_id for component in candidates},
        )
        selected.intersection_update(
            component.instance_id for component in candidates
        )
        for component in candidates:
            is_selected = component.instance_id in selected
            changed, is_selected = imgui.checkbox(
                f"{component.display_name}##merge_{component.instance_id}",
                is_selected,
            )
            if changed and is_selected:
                selected.add(component.instance_id)
            elif changed:
                selected.discard(component.instance_id)

        chosen = [
            component
            for component in candidates
            if component.instance_id in selected
        ]
        can_merge = len(chosen) >= rule.minimum_components
        if not can_merge:
            imgui.text_disabled(
                f"Select at least {rule.minimum_components} panels."
            )
        if imgui.button("Merge selected") and can_merge:
            self._actions.merge_components(rule, chosen)
            imgui.close_current_popup()
