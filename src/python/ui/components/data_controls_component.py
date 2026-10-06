from collections.abc import Iterable

from imgui_bundle import imgui

from ui.components.base_component import Component, ViewModelComponent
from ui.components.composite_component import CompositeComponent
from ui.components.date_picker_component import DatePickerComponent
from ui.components.generic_components import DateTimeComponent, GeoPosComponent
from ui.components.geo_pos_selector_component import GeoPosSelectorComponent
from ui.viewmodels.data_controls_view_model import SharedDataControlsViewModel


class DataComponentControls(Component):
    """Rendering-only common controls for one data component."""

    def __init__(self, component: Component):
        state = getattr(component, "view_model", component)
        super().__init__(state)
        self.component = component
        self.geo_pos_selector = (
            GeoPosSelectorComponent(
                on_event=lambda geo_pos: component.update(geo_pos=geo_pos),
            )
            if isinstance(component, GeoPosComponent)
            else None
        )
        self.datepicker = (
            DatePickerComponent(state)
            if isinstance(component, DateTimeComponent)
            else None
        )

    def render(self):
        state = self.state
        if self.geo_pos_selector:
            if (
                    self.component.render_geo_pos_selector
                    and self.component.render_individual_geo_pos_selector
            ):
                self.geo_pos_selector.render()
            elif self.geo_pos_selector.selecting:
                self.geo_pos_selector.cancel()

        if (
                self.datepicker
                and self.component.render_datepicker
                and self.component.render_individual_datepicker
        ):
            self.datepicker.render()
            if imgui.button("Apply Time Changes"):
                commit_edits = getattr(state, "commit_edits", None)
                if commit_edits is not None:
                    commit_edits()
                else:
                    state.changed = True

    def hide(self):
        if self.geo_pos_selector and self.geo_pos_selector.selecting:
            self.geo_pos_selector.cancel()

    def destroy(self):
        if self.geo_pos_selector:
            self.geo_pos_selector.destroy()
        if self.datepicker:
            self.datepicker.destroy()
        Component.destroy(self)


def iter_data_components(
        components: Iterable[Component],
) -> Iterable[Component]:
    for component in components:
        if isinstance(component, CompositeComponent):
            yield from iter_data_components(component.components)
        else:
            yield component


class SharedDataControlsComponent(
        ViewModelComponent[SharedDataControlsViewModel]
):
    """Composable window-wide controls backed by coordination state."""

    def __init__(self, view_model: SharedDataControlsViewModel | None = None):
        super().__init__(view_model or SharedDataControlsViewModel())
        self._datepicker: DatePickerComponent | None = None
        self._date_state = None
        self._geo_pos_selector = GeoPosSelectorComponent(
            on_event=self.view_model.update_geo_pos,
        )

    def bind(self, components: Iterable[Component]):
        leaves = tuple(iter_data_components(components))
        self.view_model.bind(
            tuple(
                getattr(component, "view_model", component)
                for component in leaves
                if isinstance(component, GeoPosComponent)
            ),
            tuple(
                getattr(component, "view_model", component)
                for component in leaves
                if isinstance(component, DateTimeComponent)
            ),
        )

    def render(self, components: Iterable[Component]) -> bool:
        leaves = tuple(iter_data_components(components))
        geo_components = tuple(
            component for component in leaves
            if isinstance(component, GeoPosComponent)
        )
        date_components = tuple(
            component for component in leaves
            if isinstance(component, DateTimeComponent)
        )
        vm = self.view_model
        self.bind(leaves)
        self.prepare_render()
        has_options = len(geo_components) > 1 or len(date_components) > 1

        if len(geo_components) > 1:
            self.checkbox_value(
                f"One position selector for all##shared_geo_{self.instance_id}",
                vm.share_geo_pos,
                vm.set_geo_sharing,
            )
        if len(date_components) > 1:
            if len(geo_components) > 1:
                imgui.same_line()
            self.checkbox_value(
                f"One date picker for all##shared_time_{self.instance_id}",
                vm.share_time,
                vm.set_time_sharing,
            )

        if not vm.share_geo_pos and self._geo_pos_selector.selecting:
            self._geo_pos_selector.cancel()
        if vm.share_geo_pos:
            self._geo_pos_selector.render()
            if vm.geo_pos is not None:
                imgui.same_line()
                imgui.text(
                    f"N {vm.geo_pos.lat_deg:.2f}°, "
                    f"E {vm.geo_pos.lon_deg:.2f}°"
                )

        if vm.date_state is not self._date_state:
            if self._datepicker is not None:
                self._datepicker.destroy()
            self._date_state = vm.date_state
            self._datepicker = (
                DatePickerComponent(vm.date_state)
                if vm.date_state is not None
                else None
            )
        if vm.share_time and self._datepicker is not None:
            self._datepicker.render()
            if imgui.button(
                    f"Apply Time Changes##shared_time_{self.instance_id}"
            ):
                vm.apply_time()

        return has_options

    def release(self, component: Component):
        self.view_model.release(
            getattr(leaf, "view_model", leaf)
            for leaf in iter_data_components((component,))
        )

    def hide(self):
        if self._geo_pos_selector.selecting:
            self._geo_pos_selector.cancel()

    def destroy(self, components: Iterable[Component] = ()):
        if self.view_model.destroyed:
            return
        if components:
            leaves = tuple(iter_data_components(components))
            self.view_model.bind(
                tuple(
                    getattr(c, "view_model", c)
                    for c in leaves if isinstance(c, GeoPosComponent)
                ),
                tuple(
                    getattr(c, "view_model", c)
                    for c in leaves if isinstance(c, DateTimeComponent)
                ),
            )
        self._geo_pos_selector.destroy()
        if self._datepicker is not None:
            self._datepicker.destroy()
            self._datepicker = None
        ViewModelComponent.destroy(self)
