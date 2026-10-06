"""Central list of component types supported by the Data window."""

from typing import NamedTuple

from ui.components.base_component import Component
from ui.components.data_graph_components import (
    PowerPlantGraphComponent,
    WeatherGraphComponent,
)
from ui.components.merged_graph_component import MergedGraphComponent


class DataComponentSpec(NamedTuple):
    label: str | None
    factory: type[Component]


# Stable keys are written to the snapshot. Add future component types here;
# use ``None`` as the label for types that should not appear in the add menu.
DATA_COMPONENT_TYPES = {
    "weather_graph": DataComponentSpec("Weather graph", WeatherGraphComponent),
    "power_graph": DataComponentSpec("Power graph", PowerPlantGraphComponent),
    "merged_graph": DataComponentSpec(None, MergedGraphComponent),
}

DATA_COMPONENT_OPTIONS = tuple(
    spec for spec in DATA_COMPONENT_TYPES.values() if spec.label is not None
)
