from typing import Any, Callable, Iterable

from scripts.user_script import (
    ExecVar,
    GraphResult,
    PlotData,
    UserScript,
    USER_SCRIPTS,
)
from service.data_streamer import AsyncDataLoader
from ui.view_model import ViewModel
from ui.viewmodels.plot_source import (
    PlotSource,
    PlotSourceKey,
    discover_plot_sources,
)


UserScriptRequest = tuple[UserScript, dict[str, ExecVar]]
UserScriptResult = tuple[UserScript, GraphResult]


def execute_user_script(request: UserScriptRequest) -> UserScriptResult:
    """Execute a user script off the UI thread and retain its identity."""
    script, args = request
    return script, script.execute(**args)

# TODO: close old window if new one is executed
class UserScriptSelectionViewModel(ViewModel):
    """Discovers plot inputs, validates selections, and executes scripts."""

    def __init__(
            self,
            component_provider: Callable[[], Iterable],
            on_result: Callable[[UserScript, Any], None],
    ):
        super().__init__()
        if not USER_SCRIPTS:
            raise ValueError("At least one user script must be configured")
        self.scripts = tuple(USER_SCRIPTS)
        self.user_script: UserScript = self.scripts[0]
        self.enabled = False
        self.selected_sources: dict[str, PlotSourceKey] = {}
        self.numeric_values = self._default_numeric_values(self.user_script)
        self.status_text = ""
        self.loading = False
        self._component_provider = component_provider
        self._on_result = on_result
        self._script_loader = AsyncDataLoader[
            UserScriptRequest,
            UserScriptResult,
        ](
            execute_user_script,
            thread_name_prefix="UserScript",
        )

    def toggle_enabled(self):
        self.enabled = not self.enabled

    def set_user_script(self, script: UserScript):
        if script is self.user_script:
            return
        self.user_script = script
        self.selected_sources.clear()
        self.numeric_values = self._default_numeric_values(script)
        self.status_text = ""

    def set_source(self, argument_name: str, source_key: PlotSourceKey):
        self.selected_sources[argument_name] = source_key

    def set_numeric_value(self, argument_name: str, value: int | float):
        argument_type = self.user_script.exec_vars.get(argument_name)
        if argument_type not in (int, float):
            raise ValueError(f"{argument_name} is not a numeric script input")
        self.numeric_values[argument_name] = argument_type(value)

    def execute(self):
        sources = self.available_plot_sources()
        try:
            args = self.build_exec_args(sources)
        except TypeError as error:
            self.status_text = str(error)
            return
        if args is None:
            self.status_text = "Not all data sources are selected"
            return
        self._script_loader.submit((self.user_script, args))
        self.loading = True
        self.status_text = "Script is running..."

    def tick(self):
        if self.destroyed:
            return
        outcome = self._script_loader.update()
        if outcome is None:
            return
        self.loading = False
        if outcome.error is not None:
            self.status_text = f"Script failed: {outcome.error}"
            return

        script, result = outcome.value
        try:
            # Creating and docking result components must happen on the UI thread.
            self._on_result(script, result)
            self.status_text = "Script executed"
        except Exception as error:
            self.status_text = f"Script failed: {error}"

    def destroy(self):
        if self.destroyed:
            return
        self._script_loader.shutdown()
        self.loading = False
        super().destroy()

    def available_plot_sources(self) -> list[PlotSource]:
        return discover_plot_sources(
            self._component_provider,
            include_composite_children=True,
        )

    def build_exec_args(
            self,
            sources: list[PlotSource],
    ) -> dict[str, ExecVar] | None:
        sources_by_key = {source.key: source for source in sources}
        exec_args = {}
        for attr_name, attr_type in self.user_script.exec_vars.items():
            if attr_type == PlotData:
                source = sources_by_key.get(self.selected_sources.get(attr_name))
                if source is None:
                    return None
                exec_args[attr_name] = source.data
            elif attr_type in (int, float):
                exec_args[attr_name] = self.numeric_values.get(
                    attr_name,
                    attr_type(0),
                )
            else:
                raise TypeError(
                    f"Unsupported UserScript input type for {attr_name}: "
                    f"{attr_type!r}",
                )
        return exec_args

    @staticmethod
    def _default_numeric_values(script: UserScript) -> dict[str, int | float]:
        return {
            attr_name: attr_type(0)
            for attr_name, attr_type in script.exec_vars.items()
            if attr_type in (int, float)
        }
