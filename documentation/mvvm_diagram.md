# UI architecture diagrams

The UI uses MVVM at both the window and component level. The first diagram
shows that general structure; the second focuses on how components are hosted
and moved by the docking system. Concrete feature implementations are omitted
to keep both diagrams suitable for a report.

## General MVVM structure

```mermaid
%%{
  init: {
    'theme': 'base',
    'htmlLabels': false,
    'themeVariables': {
      'background': '#ffffff',
      'primaryColor': '#ffffff',
      'primaryBorderColor': '#000000',
      'primaryTextColor': '#000000',
      'lineColor': '#000000',
      'textColor': '#000000',
      'noteBkgColor': '#ffffff',
      'noteBorderColor': '#000000',
      'noteTextColor': '#000000'
    }
  }
}%%
classDiagram
    direction TB

    class ViewModel {
        <<abstract>>
        +changed: bool
        +tick()
        +update(...)
        +hide()
        +destroy()
    }

    class View {
        <<abstract View>>
        +view_model: ViewModel
        +render(dt)*
    }

    class Component {
        <<abstract View fragment>>
        +render()*
        +update(...)
        +hide()
        +destroy()
    }

    class ViewModelComponent {
        <<abstract View fragment>>
        +view_model: ViewModel
        +update(...)
    }

    Component <|-- ViewModelComponent
    View ..> ViewModel : binds_to
    ViewModelComponent ..> ViewModel : binds_to
    View o-- "0..*" Component : renders_inside
```

A `View` owns the ImGui presentation. It reads UI state from its `ViewModel`
and translates user input into commands. The view model processes those
commands and accesses domain state or services through the model, but never
depends on the view. Reusable `Component` objects are presentation fragments
rendered inside a view. A stateful `ViewModelComponent` is a `Component` with
its own ViewModel binding and follows the same dependency direction.

## Docking structure

```mermaid
%%{
  init: {
    'theme': 'base',
    'htmlLabels': false,
    'themeVariables': {
      'background': '#ffffff',
      'primaryColor': '#ffffff',
      'primaryBorderColor': '#000000',
      'primaryTextColor': '#000000',
      'lineColor': '#000000',
      'textColor': '#000000',
      'noteBkgColor': '#ffffff',
      'noteBorderColor': '#000000',
      'noteTextColor': '#000000'
    }
  }
}%%
classDiagram
    direction TB

    class DataViewGroup {
        +move_to_new_window(component)
        +close_view(view)
    }

    class DataView {
        <<View>>
        +render_content()
        +remove_component(component)
    }

    class DockWindowViewModel {
        <<ViewModel>>
        +move_here(item, target, placement)
    }

    class ContentLayout {
        <<layout model>>
        +rows: tuple
    }

    class DockingWorkspace {
        <<transfer coordinator>>
        +move(component, destination)
    }

    class Component {
        <<dockable UI content>>
        +render()
    }

    DataViewGroup --> "1..*" DataView : manages
    DataView ..> DockWindowViewModel : binds
    DataView o-- "0..*" Component : renders
    DockWindowViewModel *-- "1" ContentLayout : layout
    DockWindowViewModel ..> DockingWorkspace : delegates_moves
    DataViewGroup ..> DockingWorkspace : uses
```

`DataViewGroup` manages the windows. Each `DataView` binds one
`DockWindowViewModel`, which stores its local `ContentLayout`. Cross-window
moves are delegated to `DockingWorkspace`; concrete components remain owned
and rendered by `DataView`. Rendering helpers, base classes, protocols,
validation, and cleanup paths are omitted because they do not change this main
flow.

## Moving a docked component

```mermaid
%%{
  init: {
    'theme': 'base',
    'htmlLabels': false,
    'themeVariables': {
      'background': '#ffffff',
      'primaryColor': '#ffffff',
      'primaryBorderColor': '#000000',
      'primaryTextColor': '#000000',
      'lineColor': '#000000',
      'textColor': '#000000',
      'noteBkgColor': '#ffffff',
      'noteBorderColor': '#000000',
      'noteTextColor': '#000000',
      'actorMargin': 5,
      'actorWidth': 70,
      'boxMargin': 2,
      'messageMargin': 10
    }
  }
}%%
sequenceDiagram
    actor U as User
    participant UI as UI/<br/>DataView
    participant VM as DockWindow<br/>ViewModels
    participant WS as Docking<br/>Workspace
    participant G as DataView<br/>Group

    U->>UI: Drag panel
    UI->>WS: note_drag<br/>(comp ID)

    alt Dropped in window
        UI->>VM: move_here<br/>(comp, target)
        VM->>WS: move<br/>(comp, dest)
    else Released outside
        UI->>WS: finish_frame<br/>(released)
        WS->>VM: move_to_new_<br/>window(comp)
        VM->>G: create target<br/>window
        G->>VM: move_here<br/>(comp)
        VM->>WS: move<br/>(comp, new dest)
    end

    WS->>WS: Update layouts<br/>& owner
```

For a normal drop, the `DataView` sends one `move_here` command to its view
model, which delegates the transfer to the workspace. If the panel is released
outside all windows, the UI frame asks the workspace to finish the drag. The
workspace resolves the source view model, which asks `DataViewGroup` to create
a target window and move the component there. In both cases the workspace
updates the affected layouts and the component owner. Validation, rollback,
cleanup, and empty-window handling are intentionally omitted.
