from collections.abc import Callable, Iterable

from imgui_bundle import imgui, portable_file_dialogs as pfd

from ui.components.base_component import ViewModelComponent
from ui.viewmodels.data_export_view_model import DataExportViewModel


class DataExportComponent(ViewModelComponent[DataExportViewModel]):
    """DataView-local selection and file dialog for NumPy export."""

    def __init__(
            self,
            component_provider: Callable[[], Iterable],
            view_model: DataExportViewModel | None = None,
    ):
        super().__init__(
            view_model or DataExportViewModel(component_provider)
        )
        self._save_dialog = None

    @property
    def display_name(self) -> str:
        return "NumPy export"

    def render(self):
        self._poll_dialog()
        vm = self.view_model
        self.prepare_render()

        if imgui.button("Export Data as NumPy Arrays"):
            vm.toggle_enabled()
        if not vm.enabled:
            return

        sources = vm.available_plot_sources()
        imgui.text_wrapped(
            "Select any number of time series from this Data window. "
            "Each selected series is saved as an (N, 2) NumPy array."
        )
        if not sources:
            imgui.text_disabled("No loaded time series are available.")
        else:
            if imgui.small_button("Select all"):
                vm.select_all(sources)
            imgui.same_line()
            if imgui.small_button("Clear"):
                vm.clear_selection()

            for source in sources:
                imgui.push_id(
                    f"numpy_export_{source.component_id}_{source.plot_id}"
                )
                self.checkbox_value(
                    source.display_name,
                    vm.is_selected(source.key),
                    lambda selected, key=source.key: vm.set_source_selected(
                        key,
                        selected,
                    ),
                )
                imgui.pop_id()

        selected_count = len(vm.selected_plot_sources(sources))
        imgui.begin_disabled(
            selected_count == 0 or self._save_dialog is not None
        )
        if imgui.button(f"Export selected ({selected_count})..."):
            self._save_dialog = pfd.save_file(
                "Export DataView time series",
                str(vm.destination),
                ["NumPy archive", "*.npz", "All files", "*"],
            )
        imgui.end_disabled()

        if vm.status_text:
            color = (
                (1.0, 0.35, 0.3, 1.0)
                if vm.status_is_error
                else (0.35, 0.9, 0.45, 1.0)
            )
            imgui.text_colored(color, vm.status_text)

    def _poll_dialog(self):
        if self._save_dialog is None or not self._save_dialog.ready(0):
            return
        result = self._save_dialog.result()
        self._save_dialog = None
        if result:
            self.view_model.export(result)

    def destroy(self):
        if self._save_dialog is not None:
            self._save_dialog.kill()
            self._save_dialog = None
        super().destroy()
