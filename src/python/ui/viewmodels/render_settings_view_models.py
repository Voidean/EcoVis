from model.gradient import GRADIENTS
from model.projection import Projection
from model.state.render_state import RenderState, render_state
from model.weather_type import SYNC_SCALAR
from provider import map_weather_data_repository, power_metadata_repository
from ui.view_model import ViewModel


class RenderStateViewModel(ViewModel):
    """Thin writable proxy around the renderer's shared input state."""

    def __init__(self, state: RenderState = render_state):
        super().__init__()
        self._state = state
        # ``changed`` belongs to RenderState for this proxy; do not shadow it
        # with ViewModel's default local dirty flag.
        del self.__dict__["changed"]

    def __getattr__(self, name):
        state = self.__dict__.get("_state")
        if state is not None:
            try:
                return getattr(state, name)
            except AttributeError:
                pass
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def __setattr__(self, name, value):
        state = self.__dict__.get("_state")
        if state is None or name.startswith("_") or not hasattr(state, name):
            object.__setattr__(self, name, value)
            return
        if getattr(state, name) == value:
            return
        setattr(state, name, value)
        state.changed = True
        self._after_set(name, value)

    def _after_set(self, name: str, value):
        """Apply state-specific consequences after a rendered edit."""

    def set_value(self, name: str, value) -> bool:
        if getattr(self, name) == value:
            return False
        setattr(self, name, value)
        return True

    def set_mapping_value(self, name: str, key, value) -> bool:
        values = getattr(self._state, name)
        if values.get(key) == value:
            return False
        values[key] = value
        self._state.changed = True
        return True


class MapSettingsViewModel(RenderStateViewModel):
    projections = tuple(Projection)

    def set_projection(self, projection: Projection):
        if self.set_value("projection", projection):
            self._state.camera_reset = True

    def reset_camera(self):
        self._state.camera_reset = True
        self._state.changed = True


class MapWeatherControlViewModel(RenderStateViewModel):
    def __init__(self, state: RenderState = render_state):
        super().__init__(state)
        self._repository = map_weather_data_repository()

    @property
    def scalar_data_types(self):
        return (*self._repository.data_types, SYNC_SCALAR)

    @property
    def vector_data_types(self):
        return tuple(self._repository.vector_data_types)

    @property
    def gradients(self):
        return tuple(GRADIENTS)

    @property
    def displayed_scalar_type(self):
        return (
            self.vector_data_type
            if self.scalar_data_type == SYNC_SCALAR
            else self.scalar_data_type
        )

    def _after_set(self, name: str, value):
        height_name = {
            "scalar_data_type": "scalar_height_type",
            "vector_data_type": "vector_height_type",
        }.get(name)
        if height_name is not None:
            heights = getattr(value, "heights", None)
            setattr(self, height_name, heights[0] if heights else None)

    def set_scale_range(self, start: float, end: float):
        start = min(max(float(start), 0.0), 1.0)
        end = min(max(float(end), start), 1.0)
        changed = self._state.scale_start != start or self._state.scale_end != end
        if changed:
            self._state.scale_start = start
            self._state.scale_end = end
            self._state.changed = True


class PowerPlantSettingsViewModel(RenderStateViewModel):
    def __init__(self, state: RenderState = render_state):
        super().__init__(state)
        self.plant_types = tuple(power_metadata_repository().plant_types)

    def set_plant_visible(self, plant_type: str, visible: bool):
        self.set_mapping_value("render_power_plants", plant_type, visible)

    def set_plant_color(self, plant_type: str, color):
        self.set_mapping_value("power_plant_colors", plant_type, color)
