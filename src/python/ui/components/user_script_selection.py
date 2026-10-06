from typing import Any, Callable, Iterable

from imgui_bundle import imgui

from scripts.user_script import PlotData, UserScript
from ui.components.base_component import Component, ViewModelComponent
from ui.viewmodels.user_script_view_model import UserScriptSelectionViewModel


class UserScriptSelection(ViewModelComponent[UserScriptSelectionViewModel]):
    def __init__(
            self,
            component_provider: Callable[[], Iterable[Component]],
            on_result: Callable[[UserScript, Any], None],
    ):
        super().__init__(UserScriptSelectionViewModel(
            component_provider,
            on_result,
        ))


    def render(self):
        vm = self.view_model
        self.prepare_render()
        if imgui.button("Process Data in User Script"):
            vm.toggle_enabled()

        if not vm.enabled:
            return

        available_plots = vm.available_plot_sources()

        self._combo_control(
            "User Script",
            vm.scripts,
            vm.user_script,
            vm.set_user_script,
        )

        if vm.user_script.description:
            imgui.text_wrapped(vm.user_script.description)

        for attr_name, attr_type in vm.user_script.exec_vars.items():
            # Allow the user to set any attribute on the user script.
            # The user can select data from graphs
            imgui.text(f"{attr_name}:")
            if attr_type == PlotData:
                imgui.same_line()
                self._combo_control(
                    attr_name,
                    available_plots,
                    vm.selected_sources.get(attr_name),
                    lambda value, attr_name=attr_name: vm.set_source(
                        attr_name, value,
                    ),
                    option_value=lambda source: source.key,
                    option_id=lambda source: (
                        f"plot_source_{source.component_id}_{source.plot_id}"
                    ),
                )
            elif attr_type == float:
                imgui.same_line()
                _, value = imgui.input_float(
                    f"##{attr_name}",
                    vm.numeric_values[attr_name],
                )
                vm.set_numeric_value(attr_name, value)
            elif attr_type == int:
                imgui.same_line()
                _, value = imgui.input_int(
                    f"##{attr_name}",
                    vm.numeric_values[attr_name],
                )
                vm.set_numeric_value(attr_name, value)
            else:
                imgui.same_line()
                imgui.text(f"Unsupported input type: {attr_type!r}")

        imgui.begin_disabled(vm.loading)
        execute_clicked = imgui.button("Execute Script")
        imgui.end_disabled()
        if execute_clicked:
            vm.execute()
        imgui.text(vm.status_text)
