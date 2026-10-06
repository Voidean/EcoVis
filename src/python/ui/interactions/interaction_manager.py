from abc import ABC, abstractmethod
from enum import IntEnum
from typing import List

from ui.interactions.interaction_event import InteractionEvent


class EventListener(ABC):
    @abstractmethod
    def handle_event(self, event: InteractionEvent):
        pass

    def detach(self):
        interaction_manager.remove_listener(self)

class InteractionPriority(IntEnum):
    OVERRIDE = 100
    ACTIVE_TOOL = 50
    DEFAULT = 0

class InteractionManager:
    def __init__(self):
        self._listeners: List[tuple[InteractionPriority, EventListener]] = []

    def add_listener(self, listener: EventListener, priority: InteractionPriority):
        """Adds a listener at the specified explicit priority layer."""
        # Clean up in case it's already registered to prevent duplicates
        self.remove_listener(listener)

        self._listeners.append((priority, listener))
        # Sort descending by priority (highest priority triggers first)
        self._listeners.sort(key=lambda x: x[0], reverse=True)

    def remove_listener(self, listener):
        """Removes the listener from the chain."""
        self._listeners = [(p, l) for p, l in self._listeners if l != listener]

    def dispatch(self, event):
        """Send the event down the priority chain until consumed."""
        for _, listener in self._listeners:
            listener.handle_event(event)
            if event.consumed:
                break


interaction_manager = InteractionManager()
