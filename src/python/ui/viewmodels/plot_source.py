"""Discover reusable plot-series inputs from Data window components."""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TypeAlias

from ui.viewmodels.plot_view_model import PlotSeries, PlotViewModel


__all__ = ["PlotSource", "PlotSourceKey", "discover_plot_sources"]


PlotSourceKey: TypeAlias = tuple[int, str]
ComponentSource: TypeAlias = (
    Iterable[object] | Callable[[], Iterable[object]]
)


@dataclass(frozen=True)
class PlotSource:
    component_id: int
    plot_id: str
    display_name: str
    data: PlotSeries

    @property
    def key(self) -> PlotSourceKey:
        return self.component_id, self.plot_id


def discover_plot_sources(
        component_provider_or_iterable: ComponentSource,
        *,
        include_composite_children: bool = False,
) -> list[PlotSource]:
    """Return the plot series exposed by the supplied components.

    Composite traversal is opt-in because callers may want to treat a
    composition as one opaque data source. When enabled, children are visited
    depth-first and each component object is considered at most once.
    """
    components = (
        component_provider_or_iterable()
        if callable(component_provider_or_iterable)
        else component_provider_or_iterable
    )
    sources = []
    for component in _walk_components(
            components,
            include_composite_children=include_composite_children,
    ):
        plot = getattr(component, "view_model", None)
        if not isinstance(plot, PlotViewModel):
            continue
        graph_name = plot.label or getattr(
            component,
            "display_name",
            type(component).__name__,
        )
        for plot_id, plot_data in plot.plots.items():
            sources.append(PlotSource(
                component_id=component.instance_id,
                plot_id=plot_id,
                display_name=(
                    f"{graph_name} – {plot.visible_plot_title(plot_id)}"
                ),
                data=plot_data,
            ))
    return sources


def _walk_components(
        components: Iterable[object],
        *,
        include_composite_children: bool,
) -> Iterator[object]:
    seen = set()

    def walk(component: object) -> Iterator[object]:
        identity = id(component)
        if identity in seen:
            return
        seen.add(identity)
        yield component
        if include_composite_children:
            for child in getattr(component, "components", ()):
                yield from walk(child)

    for component in components:
        yield from walk(component)
