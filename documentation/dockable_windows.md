# Dockable Data Windows

Dockable data windows are intended to be simple at the call site. A component
only has to inherit `Component`; the window group handles component
creation, extra windows, ownership, arranging, drag-and-drop, closing, and
cleanup.

## Using the UI

The main menu contains one **Data** window. Open it, then use **Add component...**
to choose another panel from the central component list.

Every dockable panel has an arrange button before its title:

- Drag the panel header to move it.
- Select `[...]` for explicit move and arrangement commands.

During a drag, highlighted arrows show exactly where the panel will be placed.
A panel can be dropped to the left or right of another panel, or into a new row
above or below it. Dropping into another data window moves the live component,
including its current settings and loaded data.

Release a dragged panel outside every data window to put it in a new window.
The same operation is available under `[...]` as **Move to a new window**.

Other useful actions are:

- **Move to another window** for a non-drag alternative.
- **Arrange in this window** for precise keyboard/mouse menu actions.
- **Reset arrangement** to stack the current panels vertically without
  resetting their data.
- The header close button or **Remove panel** to destroy a panel.
- **Merge ...** to choose compatible panels and combine them.
- **Separate ...** to restore a selected merged panel.

The **Windows** menu enables the Data window and other application windows.
The component choices shown by **Add component...** are configured in
`src/python/ui/components/data_component_options.py`:

```python
DATA_COMPONENT_TYPES = {
    "weather_graph": DataComponentSpec("Weather graph", WeatherGraphComponent),
    "power_graph": DataComponentSpec("Power graph", PowerPlantGraphComponent),
    "windrose": DataComponentSpec("Windrose", WindroseImageComponent),
}
```

To make another component available, import its class and add one entry. The
key is its stable serialization name; the class must create a fresh
`Component` when called.

## Saving Data Windows

When **Save Data Window Contents** is enabled in the configuration (the
default), closing the app stores a versioned JSON snapshot. It contains only
window positions and sizes, panel rows, stable component type keys, geographic
positions, ISO-8601 times, and the selected graph representation. Graph and
image data is recreated normally on the next start. Power graphs additionally
store their exact plant IDs and selected plant, so restoration does not depend
on the current map filters or a nearest-plant lookup.

Component type keys live in `DATA_COMPONENT_TYPES`. Additional serializable
state is added centrally with one `StateCodec` in
`ui/persistence/data_view_persistence.py`; no component-specific save method is
required.

If an extra runtime window loses its last panel, that empty window closes. The
only window in a group remains available as an empty drop target and can also
receive a new panel through **Add component...**. Closing that final window
hides the group without discarding its contents. Moving the last panel to a
new window in the same group simply replaces the old window.

## Adding a Dockable Component

The application creates the Data window once:

```python
DataViewGroup(
    ViewMetadata(ViewId.DATA, "Data"),
    WeatherGraphComponent,
    component_options=DATA_COMPONENT_OPTIONS,
)
```

For another application or feature, pass its options to `DataViewGroup` in
the same way. The group handles creation, ownership, arranging, and cleanup.

## Adding a Dockable Feature

Pass component classes or zero-argument factories to `DataViewGroup`:

```python
from ui.views.data_view_group import DataViewGroup
from ui.views.view_types import ViewId, ViewMetadata

weather_views = DataViewGroup(
    ViewMetadata(ViewId.WEATHER, "Weather"),
    WeatherGraphComponent,
)
view_registry.register(ViewId.WEATHER, weather_views)
```

These feature examples assume that the application-specific `WEATHER`,
`PLANNER`, and `REPORT` members have been added to `ViewId`.

Multiple defaults take one additional argument each:

```python
planner_views = DataViewGroup(
    ViewMetadata(ViewId.PLANNER, "Planner"),
    WeatherGraphComponent,
    WindroseImageComponent,
)
```

Use a lambda when construction needs arguments:

```python
report_views = DataViewGroup(
    ViewMetadata(ViewId.REPORT, "Report"),
    lambda: ReportComponent(show_summary=True),
)
```

Factories are important: they let the group create defaults when the user
opens another window. The factory must return a new `Component` each
time.

Rows contain at most two panels by default. Change that with one optional
argument:

```python
group = DataViewGroup(
    metadata,
    MyComponent,
    max_columns=3,
)
```

For a window with extra controls around its panels, subclass `DataView` and
pass the type:

```python
report_views = DataViewGroup(
    ViewMetadata(ViewId.REPORT, "Report"),
    ReportComponent,
    view_type=ReportView,
)
```

The subclass normally only overrides `render_content()` and calls
`super().render_content()` where the dockable panels should appear.

## Isolating Docking Workspaces

All groups which should exchange panels use the same `DockingWorkspace`.
Omitting it uses the application-wide default. A separate UI manager or test
can isolate its windows with:

```python
workspace = DockingWorkspace()
group = DataViewGroup(
    metadata,
    MyComponent,
    workspace=workspace,
)
```

For drag-out window creation, the frame owner calls:

```python
workspace.start_frame()  # directly after imgui.new_frame()

# Render all data window groups.

workspace.finish_frame(
    mouse_released=imgui.is_mouse_released(0),
    drag_payload_active=imgui.get_drag_drop_payload_py_id() is not None,
)
```

Normal menu actions and drops between windows do not require any additional
integration.

## Registering a Merge

Use the `component_merge` decorator. The decorated factory receives the
selected compatible components:

```python
@component_merge(
    "reports",
    "Merge reports",
    accepts=(ReportComponent, MergedReportComponent),
)
def merge_reports(components):
    return MergedReportComponent(components)
```

`MergedReportComponent` should inherit `CompositeComponent`. Its inherited
`release_components()` method makes separation reversible.

## Internal Layers

The docking flow has four responsibilities:

```text
DataView                    -> render panels and accept input
DockWindowViewModel        -> hold one window's layout state
DockingWorkspace           -> move panels between layouts
DataViewGroup              -> create and remove windows
```

`DataView` binds one `DockWindowViewModel`. The view model stores the local
`ContentLayout` but knows docked content only through its `DockItem` ID, so it
has no ImGui dependency. For a move, it calls the `DockingWorkspace`, which
updates the source and target layouts while preserving single ownership.
`DataViewGroup` is involved only when a window must be created or removed. The
former collection and registry classes are therefore not part of the public
flow; rendering adapters, validation, rollback, and resource cleanup remain
internal details.

## Proposed Persistence Pattern (Not Implemented)

Persistence should be an adapter around the existing runtime model, not logic
inside `ContentLayout` or individual views. The proposed format has three
parts:

1. A versioned workspace snapshot.
2. Stable component type keys and per-component state.
3. Window rows which reference component keys.

For example:

```json
{
  "version": 1,
  "groups": [
    {
      "group": "planner",
      "windows": [
        {
          "window_key": "planner-1",
          "rows": [
            ["weather-1", "windrose-1"],
            ["weather-2"]
          ]
        }
      ]
    }
  ],
  "components": {
    "weather-1": {
      "type": "weather_graph",
      "state": {}
    },
    "windrose-1": {
      "type": "windrose",
      "state": {}
    },
    "weather-2": {
      "type": "weather_graph",
      "state": {}
    }
  }
}
```

A component catalog would keep construction and state conversion explicit:

```python
component_catalog.register(
    "weather_graph",
    factory=WeatherGraphComponent,
    dump=lambda component: component.layout_state(),
    load=lambda component, state: component.apply_layout_state(state),
)
```

Restoration should happen in two passes:

1. Create every component through the catalog and apply its state.
2. Create windows and pass the resolved components into their row layouts.

This handles references and merged components without depending on Python class
names. Unknown component types can be skipped with a warning, and the
top-level `version` allows migrations.

Important design choices to decide before implementation:

- Whether component state belongs in the layout file or in a separate user
  settings file.
- Whether merged components are saved as composites or rebuilt from a merge
  rule plus child references.
- Whether window position and size should be included alongside panel rows.
- Whether snapshots are saved automatically, per named workspace, or only by
  an explicit user action.

The runtime `instance_id` must not be serialized. Persisted component and window
keys need to be stable user-data identifiers generated by the persistence
adapter.
