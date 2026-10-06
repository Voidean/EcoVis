"""Register merge behavior for graph components."""

from collections.abc import Sequence

from ui.components.base_component import Component
from ui.composition.component_merging import component_merge
from ui.components.graph_component_base import GraphComponent
from ui.components.merged_graph_component import MergedGraphComponent


@component_merge(
    "graphs",
    "Merge graphs",
    accepts=(GraphComponent, MergedGraphComponent),
)
def merge_graph_components(
        components: Sequence[Component],
) -> MergedGraphComponent:
    graphs = []
    composites = []
    for component in components:
        if isinstance(component, MergedGraphComponent):
            graphs.extend(component.graphs)
            composites.append(component)
        elif isinstance(component, GraphComponent):
            graphs.append(component)

    merged = MergedGraphComponent(graphs)
    # Transfer ownership only after construction succeeds, so a failed merge
    # leaves every source composite intact.
    for composite in composites:
        composite.release_components()
    return merged
