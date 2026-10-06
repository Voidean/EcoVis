"""Context-menu rendering for one dockable panel."""

from collections.abc import Callable

from imgui_bundle import imgui

from ui.components.base_component import Component
from ui.docking.content_layout import DockPlacement
from ui.viewmodels.dock_window_view_model import DockWindowViewModel


def render_docking_panel_menu(
        window: DockWindowViewModel[Component],
        component: Component,
        remove_component: Callable[[Component], None],
) -> bool:
    """Render panel actions and report whether the component changed window."""
    if not imgui.begin_popup("panel_actions"):
        return False

    changed_window = False
    if _menu_item("Move to a new window"):
        changed_window = window.move_to_new_window(component)

    destinations = window.workspace.available_destinations(window)
    if destinations and imgui.begin_menu("Move to another window"):
        for destination in destinations:
            if _menu_item(destination.display_name):
                changed_window = destination.move_here(component)
                break
        imgui.end_menu()

    if imgui.begin_menu("Arrange in this window"):
        if _menu_item("New row at bottom"):
            window.move_here(component, placement=DockPlacement.BOTTOM)
        _render_relative_move_menu(
            window, "Place left of", component, DockPlacement.LEFT,
        )
        _render_relative_move_menu(
            window, "Place right of", component, DockPlacement.RIGHT,
        )
        _render_relative_move_menu(
            window, "Place in row above", component, DockPlacement.ABOVE,
        )
        _render_relative_move_menu(
            window, "Place in row below", component, DockPlacement.BELOW,
        )
        imgui.end_menu()

    imgui.separator()
    if _menu_item("Remove panel"):
        remove_component(component)
        changed_window = True

    imgui.end_popup()
    return changed_window


def _render_relative_move_menu(
        window: DockWindowViewModel[Component],
        label: str,
        component: Component,
        placement: DockPlacement,
):
    targets = [
        target
        for target in window.components
        if target is not component
        and window.can_place(
            component,
            target=target,
            placement=placement,
        )
    ]
    if not targets or not imgui.begin_menu(label):
        return
    for target in targets:
        if _menu_item(f"{target.display_name}##target_{target.instance_id}"):
            window.move_here(
                component,
                target=target,
                placement=placement,
            )
            break
    imgui.end_menu()


def _menu_item(label: str) -> bool:
    return imgui.menu_item(label, "", False, True)[0]
