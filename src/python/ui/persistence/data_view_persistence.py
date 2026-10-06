"""Versioned, data-only persistence for Data views."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from model.geo_pos import GeoPos
from ui.components.base_component import Component
from ui.components.composite_component import CompositeComponent
from ui.components.data_component_options import (
    DATA_COMPONENT_TYPES,
    DataComponentSpec,
)
from ui.components.generic_components import DateTimeComponent, GeoPosComponent
from ui.components.graph_component_base import GraphComponent
from ui.components.data_graph_components import PowerPlantGraphComponent
from ui.components.data_graph_components import WeatherGraphComponent
from repository.weather_data.point_weather_data_repository import DailyType, HourlyType
from ui.views.data_view_group import DataViewGroup


@dataclass(frozen=True)
class StateCodec:
    name: str
    applies_to: type[Component]
    read: Callable[[Component], Any]
    encode: Callable[[Any], Any]
    decode: Callable[[Any], Any]


# Add another StateCodec here when more component state should be persisted.
STATE_CODECS = (
    StateCodec(
        "geo_pos",
        GeoPosComponent,
        lambda component: getattr(component, "geo_pos", None)
        or getattr(getattr(component, "plant_info", None), "pos", None),
        lambda pos: [pos.lon, pos.lat, pos.elevation],
        lambda value: GeoPos(*value),
    ),
    StateCodec(
        "start_time",
        DateTimeComponent,
        lambda component: component.start_time,
        datetime.isoformat,
        datetime.fromisoformat,
    ),
    StateCodec(
        "end_time",
        DateTimeComponent,
        lambda component: component.end_time,
        datetime.isoformat,
        datetime.fromisoformat,
    ),
    StateCodec(
        "plot_view",
        GraphComponent,
        lambda component: component.view_model.plot_view,
        str,
        str,
    ),
    StateCodec(
        "years_prior",
        GraphComponent,
        lambda component: component.view_model.years_prior,
        int,
        int,
    ),
    StateCodec(
        "weather_type",
        WeatherGraphComponent,
        lambda component: (
            component.view_model.data_frequency.__name__,
            component.view_model.data_type.name,
        ),
        list,
        lambda value: {
            "HourlyType": HourlyType,
            "DailyType": DailyType,
        }[value[0]][value[1]],
    ),
    StateCodec(
        "visualization_mode",
        WeatherGraphComponent,
        lambda component: component.view_model.visualization_mode,
        str,
        str,
    ),
    StateCodec(
        "tilt",
        WeatherGraphComponent,
        lambda component: component.view_model.tilt,
        int,
        int,
    ),
    StateCodec(
        "azimuth",
        WeatherGraphComponent,
        lambda component: (
            component.view_model.azimuth
            if isinstance(component.view_model.azimuth, int)
            else component.view_model.azimuth[0]
            if component.view_model.azimuth else 0
        ),
        int,
        int,
    ),
    StateCodec(
        "mode",
        PowerPlantGraphComponent,
        lambda component: component.view_model.mode,
        str,
        str,
    ),
    StateCodec(
        "plant_ids",
        PowerPlantGraphComponent,
        lambda component: [
            plant.plant_id for plant in component.view_model.plants
        ],
        lambda plant_ids: [int(plant_id) for plant_id in plant_ids],
        lambda plant_ids: [int(plant_id) for plant_id in plant_ids],
    ),
    StateCodec(
        "selected_plant_id",
        PowerPlantGraphComponent,
        lambda component: (
            component.view_model.plant_info.plant_id
            if component.view_model.plant_info is not None
            else None
        ),
        int,
        int,
    ),
)


def capture_data_views(
        group: DataViewGroup,
        component_types: dict[str, DataComponentSpec] = DATA_COMPONENT_TYPES,
) -> dict:
    """Return JSON-compatible descriptors; rendered graph data is excluded."""
    type_keys = {spec.factory: key for key, spec in component_types.items()}
    return {
        "version": 1,
        "windows": [
            {
                "rows": [
                    [
                        saved
                        for component in row
                        if (saved := _capture_component(
                            component,
                            type_keys,
                        )) is not None
                    ]
                    for row in window.layout_rows
                ],
                **(
                    {"position": list(window.restored_position)}
                    if window.restored_position is not None else {}
                ),
                **(
                    {"size": list(window.restored_size)}
                    if window.restored_size is not None else {}
                ),
                "shared_controls": window.shared_control_state,
            }
            for window in group.views
        ],
    }


def restore_data_views(
        group: DataViewGroup,
        snapshot,
        component_types: dict[str, DataComponentSpec] = DATA_COMPONENT_TYPES,
) -> bool:
    """Recreate components and layouts from a version-1 snapshot."""
    version = _value(snapshot, "version")
    # Keep the serialized key stable so existing saved layouts still load.
    saved_windows = _value(snapshot, "windows", [])
    if version != 1 or not saved_windows:
        return False

    created: list[Component] = []
    try:
        layouts = []
        geometries = []
        shared_states = []
        for saved_window in saved_windows:
            rows = []
            for saved_row in saved_window.get("rows", []):
                if len(saved_row) > group.max_columns:
                    raise ValueError("Saved row exceeds the column limit")
                row = [
                    _restore_component(saved, component_types, created)
                    for saved in saved_row
                ]
                if row:
                    rows.append(row)
            if rows:
                layouts.append(rows)
                geometries.append((
                    _geometry(saved_window.get("position")),
                    _geometry(saved_window.get("size")),
                ))
                shared_states.append(saved_window.get("shared_controls", {}))
        if not layouts:
            return False
        group.restore_views(layouts)
        for window, (position, size) in zip(group.views, geometries):
            window.restored_position = position
            window.restored_size = size
        for window, shared_state in zip(group.views, shared_states):
            window.restore_shared_control_state(shared_state)
        return True
    except (KeyError, TypeError, ValueError):
        owned_ids = {
            id(child)
            for component in created
            if isinstance(component, CompositeComponent)
            for child in component.components
        }
        for component in created:
            if (
                    id(component) not in owned_ids
                    and group.workspace.owner_of(component) is None
            ):
                component.destroy()
        return False


def _capture_component(component, type_keys) -> dict | None:
    """Describe a reconstructible Component, or omit transient content."""
    key = type_keys.get(type(component))
    if key is None:
        return None
    descriptor = {"type": key}
    state = {}
    for codec in STATE_CODECS:
        if isinstance(component, codec.applies_to):
            value = codec.read(component)
            if value is not None:
                state[codec.name] = codec.encode(value)
    if state:
        descriptor["state"] = state
    if isinstance(component, CompositeComponent):
        children = [
            _capture_component(child, type_keys)
            for child in component.components
        ]
        # A partial composite would not represent what the user saved and may
        # violate the concrete composite's minimum-child invariant.
        if not children or any(child is None for child in children):
            return None
        descriptor["components"] = children
    return descriptor


def _restore_component(saved, component_types, created):
    spec = component_types[saved["type"]]
    children = [
        _restore_component(child, component_types, created)
        for child in saved.get("components", [])
    ]
    component = spec.factory(children) if children else spec.factory()
    created.append(component)
    state = saved.get("state", {})
    updates = {
        codec.name: codec.decode(state[codec.name])
        for codec in STATE_CODECS
        if codec.name in state and isinstance(component, codec.applies_to)
    }
    weather_type = updates.pop("weather_type", None)
    if weather_type is not None:
        updates["data_frequency"] = type(weather_type)
        updates["data_type"] = weather_type
    if updates:
        component.update(**updates)
    return component


def _value(node, name, default=None):
    return node.get(name, default) if isinstance(node, dict) else getattr(node, name, default)


def _geometry(value):
    if value is None or len(value) != 2:
        return None
    return float(value[0]), float(value[1])
