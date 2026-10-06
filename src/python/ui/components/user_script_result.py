from typing import Any

from scripts.user_script import UserScript
from ui.components.base_component import Component
from ui.components.plot_component import UserScriptGraphComponent


def create_result_component(
        script: UserScript,
        result: Any,
) -> Component:
    """Create the graph component returned by a user script."""
    if not isinstance(result, dict):
        raise TypeError("A user script must return a dictionary of plots")
    return UserScriptGraphComponent(script.display_name, result)
