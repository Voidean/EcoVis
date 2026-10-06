# User Interface Architecture

The user interface is built using ImGui and follows a loosely coupled architecture. UI components do not directly modify rendering objects or scene data. Instead, they update shared state objects, which are then processed by the `SceneController`.

## Architecture Overview

```text
UI Windows
    ↓
State Objects
(RenderState, TimeState)
    ↓
Dirty Flag (changed)
    ↓
SceneController
    ↓
Scene / Shaders / Data Streamers
```

This approach separates presentation logic from rendering and simulation logic, making the UI independent from the underlying scene implementation.

## State-Based Communication

The UI primarily interacts with two state objects like:

- `RenderState`
- `TimeState`

Whenever a user changes a setting, the corresponding state value is updated and the `changed` flag is set:

```python
self.state.changed = True
```

The `SceneController` monitors these flags during the update loop and applies the necessary changes to the scene.

This pattern avoids direct dependencies between UI widgets and rendering code.

## UI Manager

The `UIManager` acts as the central entry point for all ImGui windows.

It owns the shared state objects and creates the individual window instances:

```python
self.time_state = TimeState()
self.render_state = RenderState()
```

During rendering it simply forwards execution to all registered windows:

```python
self.time_control_window.render()
self.render_settings_window.render()
...
```

## Window View Base Class

Most UI windows inherit from the common `WindowView` base class. It owns the
ImGui window scope and binds a `ViewLifecycleViewModel` for visibility and
closing behavior; concrete views provide only their contents and resource
lifecycle hooks.

The base class provides reusable helper methods for common ImGui controls such as:

- Checkboxes
- Sliders
- Colour pickers
- Combo boxes

These helpers automatically:

1. Read values from the associated state object
2. Update the state when the user changes a value
3. Set the dirty flag (`state.changed = True`)

This eliminates repetitive boilerplate code throughout the UI implementation.

## Dockable Window Contents

`DataViewGroup` is the small public API for dockable features. Component
classes or factories are declared once; the group then creates windows and
handles their lifecycle. Moving a panel transfers its live component instance,
so its state, loaded data, and synchronization links are retained.

Each `DataView` binds a `DockWindowViewModel`. The view model extends
`ViewLifecycleViewModel`, owns the window-local item order, active selection,
and pure `ContentLayout`, and exposes commands for layout changes. Docked
content reaches it only through the small `DockItem` identity protocol; the
view model neither imports nor creates or destroys concrete `Component`
objects. `DockingWorkspace` is an injected application service for the
invariants that span windows: it keeps the private component-owner index and
applies transfers atomically. There is no separate registry or collection
layer.

`DataView` also owns a `DockingRenderer`. This is a plain ImGui adapter rather
than a `Component` subtype: it reads the `DockWindowViewModel` and translates
panel menus and drag-and-drop input into view-model commands. Component
creation, merge/split composition, rendering, and destruction stay in
`DataView`, which is also notified synchronously after ownership changes so it
can release obsolete rendering controls. `DataViewGroup` manages the runtime
`DataView` instances and implements the
`DockWindowManager` protocol used by view models when a component needs a new
window or leaves its source window empty. See
[Dockable Data Windows](dockable_windows.md) for the user controls, extension
examples, and persistence format.

Common date and location controls are owned by `DataComponentControls`.
This keeps those controls independent of both the containing window and the
concrete data component. A window can independently share its position selector
or date picker across all compatible contents. Composite contents participate
through their retained children, so shared controls also work after graphs are
merged.

Component families can register merge rules with the
`ComponentMergeRegistry`. The graph rule creates a reversible merged graph:
each child graph retains its own data settings and synchronization behavior,
while their series are drawn in one ImPlot. Series with different value units
use separate Y axes (up to ImPlot's three available Y axes). Separating the
merged graph restores the original sections.

Selectable graph representations form a second MVVM layer below each weather
or power graph. The owning `GraphViewModel` retains the unmodified arrays loaded
from its repository. A `GraphDisplayViewModel` derives cached presentation data
for one representation, while its matching content component chooses the
ImPlot primitive. Switching representations therefore neither changes the raw
arrays nor submits another repository request. Line, scatter, area, histogram,
calendar-heatmap, and distribution views use this mechanism;
the power graph additionally registers cumulative energy yield. Calendar
matrices are rendered as aligned small multiples with one shared color scale,
because overlaying multiple heatmaps would hide all but the last dataset, and
their columns are limited to the loaded time range. Scatter shows binned
absolute frequency, while area views shade timestamp-aligned differences
between series. The mean-squared-error view plots the running mean of those
squared, timestamp-aligned differences. Frequency and fitted-distribution
views can locally exclude zero values and report their share without changing
the source arrays.

## Benefits of the Design

This architecture provides several advantages:

- Loose coupling between UI and rendering systems
- Simple synchronization through shared state objects
- Easy addition of new windows and settings
- Centralized scene updates through the `SceneController`
- Clear separation of responsibilities between presentation and application logic
