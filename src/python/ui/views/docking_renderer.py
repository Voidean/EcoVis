"""ImGui rendering adapter for a dock-window view model."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.components.docking_merge_controls import DockingMergeControls
from ui.components.docking_panel_menu import render_docking_panel_menu
from ui.docking.content_layout import DockPlacement
from ui.viewmodels.dock_window_view_model import DockWindowViewModel

if TYPE_CHECKING:
    from ui.views.data_view import DataView


COMPONENT_DRAG_PAYLOAD = "WINDOW_COMPONENT"


class DockingRenderer:
    """Translate ImGui interactions into dock-window view-model commands."""

    def __init__(
            self,
            view_model: DockWindowViewModel[Component],
            actions: DataView,
            component_options: Sequence[tuple[str, Callable[[], Component]]] = (),
    ):
        self.view_model = view_model
        self._actions = actions
        self._component_options = tuple(component_options)
        self._expanded: dict[int, bool] = {}
        self._merge_controls = DockingMergeControls(view_model, actions)

    def render(self):
        self._note_hovered_host()
        self._render_help()
        self._merge_controls.render()

        if not self.view_model.components:
            self._render_empty_drop_target()
            return

        for row_index, row in enumerate(self.view_model.layout_rows):
            row_components = [
                component
                for component in row
                if self.view_model.contains(component)
            ]
            if not row_components:
                continue

            if row_index == 0:
                self._render_row_drop_target(
                    row_components,
                    DockPlacement.ABOVE,
                )

            collapsed, expanded = [], []
            for component in row_components:
                target = (
                    expanded
                    if self._expanded.get(component.instance_id, True)
                    else collapsed
                )
                target.append(component)

            for component in collapsed:
                self._render_component_panel(component)

            if len(expanded) == 1:
                self._render_component_panel(expanded[0])
            elif len(expanded) > 1 and imgui.begin_table(
                    self._table_id(row_components),
                    len(expanded),
                    imgui.TableFlags_.sizing_stretch_prop
                    | imgui.TableFlags_.borders_inner_v
                    | imgui.TableFlags_.resizable,
            ):
                for component in expanded:
                    imgui.table_setup_column(
                        f"{component.display_name}##column_{component.instance_id}",
                        imgui.TableColumnFlags_.width_stretch,
                        1.0,
                        component.instance_id,
                    )
                imgui.table_next_row()
                for component in expanded:
                    imgui.table_next_column()
                    self._render_component_panel(component)
                imgui.end_table()

            current_row = self._current_row(row_components)
            if current_row:
                self._render_row_drop_target(
                    current_row,
                    DockPlacement.BELOW,
                )
            imgui.separator()

    def _render_help(self):

        if self._component_options:
            if imgui.button("Add component..."):
                imgui.open_popup("add_component")
            imgui.same_line()
            imgui.text_disabled(
                "Drag panel headers to arrange panels; use [...] for actions "
                f"(max {self.view_model.layout.max_columns} per row)."
            )
            if imgui.begin_popup("add_component"):
                for label, factory in self._component_options:
                    if self._menu_item(label):
                        self._actions.add_component(factory)
                        break
                imgui.end_popup()
        if len(self.view_model.components) > 1:
            imgui.same_line()
            if imgui.small_button(
                    f"Reset arrangement##layout_{self.view_model.instance_id}"
            ):
                self.view_model.reset_layout()
            if imgui.is_item_hovered():
                imgui.set_tooltip(
                    "Stack the current panels vertically without resetting their data."
                )

    def _render_component_panel(
            self,
            component: Component,
    ):
        if not self.view_model.contains(component):
            return

        imgui.push_id(component.instance_id)
        imgui.set_next_item_open(
            self._expanded.get(component.instance_id, True),
            imgui.Cond_.always,
        )
        expanded, is_visible = imgui.collapsing_header(
            component.display_name,
            True,
            imgui.TreeNodeFlags_.default_open,
        )
        header_clicked = imgui.is_item_clicked()
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "Drag this panel header to arrange it.\n"
                "Release outside every data window to create a new window."
            )

        header_min = imgui.get_item_rect_min()
        header_max = imgui.get_item_rect_max()
        style = imgui.get_style()
        button_width = imgui.calc_text_size("...").x + style.frame_padding.x * 2
        button_height = imgui.get_frame_height()
        imgui.set_cursor_screen_pos(
            (
                header_max.x - button_width - style.item_spacing.x - 20.0,
                header_min.y + max(0.0, (header_max.y - header_min.y - button_height) / 2.0),
            )
        )
        if imgui.small_button("..."):
            imgui.open_popup("panel_actions")
        if imgui.is_item_hovered():
            imgui.set_tooltip("Move, arrange, or remove this panel.")

        self._render_drag_source(component)
        if header_clicked:
            self.view_model.activate(component)
        self._expanded[component.instance_id] = expanded

        changed_host = render_docking_panel_menu(
            self.view_model,
            component,
            self._actions.remove_component,
        )
        if not is_visible and self.view_model.contains(component):
            self._actions.remove_component(component)
            changed_host = True

        if changed_host or not self.view_model.contains(component):
            imgui.pop_id()
            return

        # Only reposition for content after actions which may remove or move
        # the panel. Returning immediately after SetCursorScreenPos without
        # submitting another item makes ImGui assert at the next table column.
        imgui.set_cursor_screen_pos(
            (header_min.x, header_max.y + style.item_spacing.y)
        )
        # Establish the new layout position even when the panel is collapsed
        # and no drag target or component content is rendered afterwards.
        imgui.dummy((0.0, 0.0))
        self._render_side_drop_targets(component)
        if expanded:
            self._actions.render_component(component)
        else:
            self._actions.hide_component_controls(component)
        imgui.pop_id()

    def _render_drag_source(self, component: Component):
        if not imgui.begin_drag_drop_source():
            return
        payload_id = component.instance_id
        self.view_model.workspace.note_drag(payload_id)
        imgui.set_drag_drop_payload_py_id(
            COMPONENT_DRAG_PAYLOAD,
            payload_id,
            imgui.Cond_.once,
        )
        imgui.text(f"Move {component.display_name}")
        imgui.text_disabled(
            "Drop on an arrow, another window, or outside all data views."
        )
        imgui.end_drag_drop_source()

    def _render_side_drop_targets(self, target: Component):
        dragged = self._dragged_component()
        if dragged is None or dragged is target:
            return

        placements = [
            (DockPlacement.LEFT, "← Drop left"),
            (DockPlacement.RIGHT, "Drop right →"),
        ]
        available = [
            (placement, label)
            for placement, label in placements
            if self.view_model.can_place(
                dragged,
                target=target,
                placement=placement,
            )
        ]
        if not available:
            return

        if imgui.begin_table(
                f"side_drop_targets_{target.instance_id}",
                len(available),
                imgui.TableFlags_.sizing_stretch_same,
        ):
            for placement, label in available:
                imgui.table_next_column()
                self._render_drop_target(
                    label,
                    target=target,
                    placement=placement,
                )
            imgui.end_table()

    def _render_row_drop_target(
            self,
            row: Sequence[Component],
            placement: DockPlacement,
    ):
        dragged = self._dragged_component()
        if dragged is None:
            return
        candidates = reversed(row) if placement is DockPlacement.BELOW else row
        target = next(
            (component for component in candidates if component is not dragged),
            None,
        )
        if target is None:
            return
        self._render_drop_target(
            (
                "↓ Drop into a new row below"
                if placement is DockPlacement.BELOW
                else "↑ Drop into a new row above"
            ),
            target=target,
            placement=placement,
        )

    def _render_empty_drop_target(self):
        if self._dragged_component() is None:
            imgui.text_disabled(
                "No content yet. Use 'Add component...' above to choose what to display."
                if self._component_options
                else "No content"
            )
            return
        self._render_drop_target(
            "Drop panel here",
            target=None,
            placement=DockPlacement.BOTTOM,
        )

    def _render_drop_target(
            self,
            label: str,
            *,
            target: Component | None,
            placement: DockPlacement,
    ):
        highlight = imgui.get_style_color_vec4(imgui.Col_.drag_drop_target)
        imgui.push_style_color(imgui.Col_.button, highlight)
        imgui.push_style_color(imgui.Col_.button_hovered, highlight)
        imgui.button(
            f"{label}##{placement}_{getattr(target, 'instance_id', 'window')}",
            (-1.0, 0.0),
        )
        imgui.pop_style_color(2)

        if imgui.begin_drag_drop_target():
            payload = imgui.accept_drag_drop_payload_py_id(
                COMPONENT_DRAG_PAYLOAD
            )
            if payload is not None and imgui.is_mouse_released(0):
                component = self.view_model.workspace.resolve_component(
                    payload.data_id,
                )
                if component is not None:
                    self.view_model.workspace.note_drop_accepted()
                    self.view_model.move_here(
                        component,
                        target=target,
                        placement=placement,
                    )
            imgui.end_drag_drop_target()

    def _dragged_component(self) -> Component | None:
        payload = imgui.get_drag_drop_payload_py_id()
        if payload is None or payload.type != COMPONENT_DRAG_PAYLOAD:
            return None
        return self.view_model.workspace.resolve_component(payload.data_id)

    def _note_hovered_host(self):
        payload = imgui.get_drag_drop_payload_py_id()
        if payload is None or payload.type != COMPONENT_DRAG_PAYLOAD:
            return
        flags = (
            imgui.HoveredFlags_.root_and_child_windows
            | imgui.HoveredFlags_.allow_when_blocked_by_active_item
        )
        if imgui.is_window_hovered(flags):
            self.view_model.workspace.note_host_hovered()

    def _current_row(
            self,
            components: Sequence[Component],
    ) -> tuple[Component, ...] | None:
        component_ids = {component.instance_id for component in components}
        return next(
            (
                row
                for row in self.view_model.layout_rows
                if any(
                    component.instance_id in component_ids
                    for component in row
                )
            ),
            None,
        )

    def _table_id(
            self,
            components: Sequence[Component],
    ) -> str:
        component_ids = "_".join(
            str(component.instance_id) for component in components
        )
        return (
            f"content_row_{component_ids}_{self.view_model.instance_id}"
        )

    @staticmethod
    def _menu_item(label: str, *, enabled: bool = True) -> bool:
        return imgui.menu_item(label, "", False, enabled)[0]

    def destroy(self):
        self._expanded.clear()
        self._merge_controls.destroy()
