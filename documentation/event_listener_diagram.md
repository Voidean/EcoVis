# Event listener architecture

The interaction system decouples raw SDL input from application-specific
actions. `Input` converts relevant keyboard and mouse input into small event
objects and passes them to a central `InteractionManager`. The manager then
offers each event to registered listeners in descending priority order.

## Class structure

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

    class Input {
        +process_event(event: InteractionEvent)
        +handle_key_press(key)
    }

    class InteractionManager {
        +add_listener(listener: EventListener, priority: InteractionPriority)
        +remove_listener(listener)
        +dispatch(event)
    }

    class InteractionPriority {
        <<enumeration>>
        OVERRIDE = 100
        ACTIVE_TOOL = 50
        DEFAULT = 0
    }

    class EventListener {
        <<abstract>>
        +handle_event(event)*
        +detach()
    }

    class InteractionEvent {
        +consumed: bool
        +consume()
    }

    class MouseEvent {
        +button
        +mouse_pos
        +world_pos
    }

    class KeyEvent {
        +key
    }

    Input ..> InteractionManager : dispatches_events_to
    InteractionManager *-- "0..*" EventListener : listeners
    InteractionManager ..> InteractionPriority : uses
    InteractionManager ..> InteractionEvent : dispatches

    InteractionEvent <|-- MouseEvent
    InteractionEvent <|-- KeyEvent
```

`EventListener` defines the common callback contract and provides `detach()`
for unregistering a listener. `InteractionManager` stores each listener
together with an `InteractionPriority`. Adding an already registered listener
first removes its previous entry, which prevents duplicate callbacks. The list
is sorted whenever a listener is added, so `dispatch()` can traverse it without
performing additional priority calculations.

`InteractionEvent` contains the shared `consumed` state. `MouseEvent` adds the
clicked button as well as the screen and world positions.
`KeyEvent` contains the
pressed key. More event types can be added without changing the manager or
existing listeners.

## Event dispatch

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
      'actorBkg': '#ffffff',
      'actorBorder': '#000000',
      'actorTextColor': '#000000',
      'signalColor': '#000000',
      'signalTextColor': '#000000'
    }
  }
}%%
sequenceDiagram
    participant SDL
    participant Input
    participant Manager as InteractionManager
    participant Active as Active-tool listener
    participant Default as Default listener

    SDL->>Input: Keyboard or mouse input
    Input->>Input: Ignore input captured by ImGui
    Input->>Manager: dispatch(InteractionEvent)
    Manager->>Active: handle_event(event)

    alt Active listener consumes event
        Active->>Active: event.consume()
        Manager-->>Input: Stop dispatch
    else Event remains unconsumed
        Manager->>Default: handle_event(event)
        opt Default listener handles event exclusively
            Default->>Default: event.consume()
        end
        Manager-->>Input: Dispatch complete
    end
```

An active tool uses `InteractionPriority.ACTIVE_TOOL`, while persistent
features use `InteractionPriority.DEFAULT`. For example, the geographic
position selector temporarily registers as an active tool. It therefore sees
a click before the measurement-point view model. If it consumes that click,
the lower-priority listener is not called.

## Listener lifecycle

Persistent listeners register during initialization and call `detach()` from
their `destroy()` method. Temporary tools register only while active. The
geographic position selector follows this lifecycle:

1. `start_selecting()` registers the view model with `ACTIVE_TOOL` priority.
2. `handle_event()` processes the next suitable left-click event.
3. `stop_selecting()` detaches the listener after a selection or cancellation.
4. `destroy()` also stops selection, ensuring that no obsolete listener remains
   registered.

This explicit lifecycle is important because the manager stores references to
its listeners. A destroyed view model that is not detached could continue to
receive events and would also remain reachable through the manager.

## Input filtering

The listener system receives only application input. `Input` checks ImGui's
keyboard and mouse capture flags before creating or dispatching an interaction
event. Mouse events are dispatched only for clicks below the drag threshold;
camera drags remain part of the continuous input state. This prevents actions
on the map while the user interacts with a UI control.
