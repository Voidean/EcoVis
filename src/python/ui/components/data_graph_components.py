from ui.components.generic_components import GeoPosComponent
from ui.components.graph_component_base import GraphComponent
from ui.components.graph_controls_component import (
    PowerPlantGraphControlsComponent,
    WeatherGraphControlsComponent,
)
from ui.viewmodels.power_graph_view_model import PowerPlantGraphViewModel
from ui.viewmodels.weather_graph_view_model import WeatherGraphViewModel


class PowerPlantGraphComponent(GraphComponent, GeoPosComponent):
    def __init__(self):
        view_model = PowerPlantGraphViewModel()
        GraphComponent.__init__(
            self,
            view_model,
            PowerPlantGraphControlsComponent(view_model),
        )

class WeatherGraphComponent(GraphComponent, GeoPosComponent):
    def __init__(self):
        view_model = WeatherGraphViewModel()
        GraphComponent.__init__(
            self,
            view_model,
            WeatherGraphControlsComponent(view_model),
        )
