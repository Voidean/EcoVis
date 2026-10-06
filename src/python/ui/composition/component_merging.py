from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from ui.components.base_component import Component


@dataclass(frozen=True)
class ComponentMergeRule:
    """A merge operation registered by a component family."""
    identifier: str
    label: str
    accepts: Callable[[Component], bool]
    merge: Callable[[Sequence[Component]], Component]
    minimum_components: int = 2


class ComponentMergeRegistry:
    """Keeps component containers independent from concrete merge types."""

    def __init__(self):
        self._rules: dict[str, ComponentMergeRule] = {}

    def register(self, rule: ComponentMergeRule):
        self._rules[rule.identifier] = rule

    def available_merges(
            self,
            components: Sequence[Component],
    ) -> list[tuple[ComponentMergeRule, list[Component]]]:
        available = []
        for rule in self._rules.values():
            candidates = [component for component in components if rule.accepts(component)]
            if len(candidates) >= rule.minimum_components:
                available.append((rule, candidates))
        return available


component_merge_registry = ComponentMergeRegistry()


ComponentType: TypeAlias = (
    type[Component]
    | tuple[type[Component], ...]
)


def component_merge(
        identifier: str,
        label: str,
        *,
        accepts: ComponentType,
        minimum_components: int = 2,
):
    """Register a component merge with a small, declarative decorator.

    Example::

        @component_merge("graphs", "Merge graphs", accepts=GraphComponent)
        def merge_graphs(components):
            return MergedGraphComponent(components)
    """
    def register(
            merge: Callable[[Sequence[Component]], Component],
    ):
        component_merge_registry.register(ComponentMergeRule(
            identifier=identifier,
            label=label,
            accepts=lambda component: isinstance(component, accepts),
            merge=merge,
            minimum_components=minimum_components,
        ))
        return merge

    return register
