from collections.abc import Callable
from typing import Any

from model.geo_pos import GeoPos
from model.state.render_state import render_state
from provider import elevation_api
from ui.interactions.interaction_event import InteractionEvent, MouseEvent
from ui.interactions.interaction_manager import (
    EventListener,
    InteractionPriority,
    interaction_manager,
)
from ui.view_model import ViewModel
from util.geo_projection import calculate_geo_pos_from_click
from util.input_constants import MouseButton


class GeoPosSelectorViewModel(ViewModel, EventListener):
    """Owns the map-selection interaction independently of its button UI."""

    def __init__(
            self,
            on_selected: Callable[[GeoPos], Any] = lambda _position: None,
            consume: bool = False,
    ):
        super().__init__()
        self.on_selected = on_selected
        self.consume = consume
        self.selecting = False

    def start_selecting(self):
        if self.destroyed or self.selecting:
            return
        interaction_manager.add_listener(self, InteractionPriority.ACTIVE_TOOL)
        self.selecting = True

    def stop_selecting(self):
        self.detach()
        self.selecting = False

    def handle_event(self, event: InteractionEvent):
        if not isinstance(event, MouseEvent) or event.button != MouseButton.LEFT:
            return
        geo_pos = calculate_geo_pos_from_click(
            event.world_pos,
            render_state.projection,
        )
        if geo_pos is not None:
            geo_pos.elevation = elevation_api().get_elevation(
                geo_pos
            ).elevation
            self.on_selected(geo_pos)
            self.stop_selecting()
        if self.consume:
            event.consume()

    def destroy(self):
        if self.destroyed:
            return
        self.stop_selecting()
        super().destroy()
