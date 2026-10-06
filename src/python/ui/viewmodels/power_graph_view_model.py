from model.data_requests import GraphPlotRequest, PowerPlotRequest
from model.geo_pos import GeoPos
from model.power_plant import PowerPlant
from model.state.render_state import render_state
from provider import power_metadata_repository, power_timeseries_repository
from ui.viewmodels.graph_display.time_series import CumulativeYieldViewModel
from ui.viewmodels.graph_view_model import GraphViewModel
from ui.viewmodels.plot_view_model import Plots
from util.plotting_util import convert_datetime_arrays_to_plot
from util.coordinate_conversion import haversine_distance
from util.time_util import safe_year_replace


class PowerPlantGraphViewModel(GraphViewModel):
    def __init__(self):
        super().__init__()
        self.label = "Power Yield"
        self.display_name = "Power Plant Graph"
        self.label_y = "Power [kW]"
        self.get_title = self._power_plot_title
        self.plants: list[PowerPlant] = []
        self.plant_info: PowerPlant | None = None
        self.geo_pos: GeoPos | None = None
        self.mode = "Measurements"
        self.add_plot_view(CumulativeYieldViewModel(self))
        self.render_geo_pos_selector = True
        self.render_individual_geo_pos_selector = True

    def update(
            self,
            geo_pos=None,
            plant_ids=None,
            selected_plant_id=None,
            mode=None,
            **kwargs,
    ):
        if plant_ids is not None:
            self.restore_plants(plant_ids, selected_plant_id)
        elif geo_pos is not None:
            self.add_nearest_plant(geo_pos)
        if mode is not None:
            self.set_mode(mode)
        super().update(**kwargs)

    def restore_plants(
            self,
            plant_ids: list[int],
            selected_plant_id: int | None = None,
    ):
        """Restore exact plants without depending on map render filters."""
        unique_plant_ids = list(dict.fromkeys(map(int, plant_ids)))
        plants = [
            plant
            for plant_id in unique_plant_ids
            if (plant := power_metadata_repository().get_plant_by_id(
                plant_id,
            )) is not None
        ]
        self.plants = plants
        self.plant_info = next(
            (
                plant
                for plant in self.plants
                if plant.plant_id == selected_plant_id
            ),
            self.plants[0] if self.plants else None,
        )
        self.geo_pos = self.plant_info.pos if self.plant_info else None
        self.highlighted = (
            self.plant_info.plant_id if self.plant_info else None
        )
        self.changed = True

    def sync(self):
        from ui.viewmodels.weather_graph_view_model import WeatherGraphViewModel

        if isinstance(self.host, WeatherGraphViewModel):
            if "Time" in self.sync_mode:
                self.start_time = self.host.start_time
                self.end_time = self.host.end_time
            if "Location" in self.sync_mode:
                self.plants.clear()
                self.add_nearest_plant(self.host.geo_pos)
        elif isinstance(self.host, PowerPlantGraphViewModel):
            if "Time" in self.sync_mode:
                self.start_time = self.host.start_time
                self.end_time = self.host.end_time
            if "Location" in self.sync_mode:
                self.plants = self.host.plants.copy()
                self.plant_info = (
                    self.host.plant_info
                    if self.host.plant_info in self.plants
                    else self.plants[0] if self.plants else None
                )
                self.geo_pos = (
                    self.plant_info.pos if self.plant_info else None
                )
                self.highlighted = (
                    self.plant_info.plant_id if self.plant_info else None
                )
        self.changed = True

    def displayed_plots(self) -> Plots:
        if self.mode == "Comparison":
            return self.plots
        prefix = f"{self.mode.lower()}:"
        return {
            plot_id: plot_data
            for plot_id, plot_data in self.plots.items()
            if str(plot_id).startswith(prefix)
        }

    def set_mode(self, mode: str):
        if mode == self.mode:
            return
        self.mode = mode
        self._invalidate_visible_plots()
        self.update_plot_bounds()

    def select_plant(self, plant: PowerPlant):
        if plant not in self.plants or plant is self.plant_info:
            return
        self.plant_info = plant
        self.geo_pos = plant.pos
        self.highlighted = plant.plant_id
        self.update_links()

    def remove_selected_plant(self):
        selected = self.plant_info
        if selected is None or selected not in self.plants:
            return
        self.plants.remove(selected)
        self.plant_info = self.plants[0] if self.plants else None
        self.geo_pos = self.plant_info.pos if self.plant_info else None
        self.changed = True

    def add_nearest_plant(self, geo_pos: GeoPos | None):
        if geo_pos is None:
            return
        active_types = [
            plant_type
            for plant_type, enabled in render_state.render_power_plants.items()
            if enabled
        ]
        plant = power_metadata_repository().find_nearest_plant_by_energy_sources(
            lat=geo_pos.lat_deg,
            lon=geo_pos.lon_deg,
            allowed_sources=active_types,
        )
        if not plant or plant in self.plants:
            return
        if haversine_distance(geo_pos, plant.pos) > 200000:
            return
        self.plants.append(plant)
        self.plant_info = plant
        self.geo_pos = plant.pos
        self.changed = True

    def reload_plot(self):
        self._submit_plot_load(PowerPlotRequest(
            plants=[plant.plant_id for plant in self.plants],
            start_time=self.start_time,
            end_time=self.end_time,
            years_prior=self.years_prior,
        ))

    @staticmethod
    def _load_power_plots(request: PowerPlotRequest) -> Plots:
        plot_data = {}
        for plant_id in request.plants:
            for year_offset in range(request.years_prior + 1):
                plot_start = safe_year_replace(
                    request.start_time,
                    request.start_time.year - year_offset,
                )
                plot_end = safe_year_replace(
                    request.end_time,
                    request.end_time.year - year_offset,
                )
                measurement_data = power_timeseries_repository().get_values_for_range(
                    plant_id,
                    start_dt=plot_start,
                    end_dt=plot_end,
                )
                prognosis_data = power_timeseries_repository().get_values_for_range(
                    plant_id,
                    start_dt=plot_start,
                    end_dt=plot_end,
                    prognosis=True,
                )
                suffix = f"{plant_id}:{plot_start.year}"
                for kind, data in (
                    ("measurements", measurement_data),
                    ("prognosis", prognosis_data),
                ):
                    if data.values.size == 0:
                        continue
                    timestamps = [
                        safe_year_replace(timestamp, timestamp.year + year_offset)
                        for timestamp in data.timestamps
                    ]
                    plot_data[f"{kind}:{suffix}"] = convert_datetime_arrays_to_plot(
                        timestamps,
                        data.values,
                    )
        return plot_data

    def _load_plot_request(self, request: GraphPlotRequest) -> Plots:
        if not isinstance(request, PowerPlotRequest):
            raise TypeError("Power graph received a non-power request")
        return self._load_power_plots(request)

    def _refresh_derived_state(self):
        super()._refresh_derived_state()
        self.render_geo_pos_selector = (
            not self.host or "Location" not in self.sync_mode
        )
        if self.plant_info not in self.plants:
            self.plant_info = self.plants[0] if self.plants else None
        self.geo_pos = self.plant_info.pos if self.plant_info else None
        self.highlighted = (
            self.plant_info.plant_id if self.plant_info else None
        )

    def _display_revision_token(self) -> tuple:
        return self.mode,

    @staticmethod
    def _distribution_maximum(plot_id, values):
        _, plant_id, _ = PowerPlantGraphViewModel._power_plot_parts(plot_id)
        plant = power_metadata_repository().get_plant_by_id(int(plant_id))
        capacity = plant.leistung_kw if plant is not None else 0.0
        return max(capacity or 0, values.max())

    @staticmethod
    def _power_plot_title(key):
        data_kind, plant_id, year = PowerPlantGraphViewModel._power_plot_parts(key)
        plant = power_metadata_repository().get_plant_by_id(int(plant_id))
        return f"{plant} ({year}, {data_kind.title()})"

    @staticmethod
    def _power_plot_parts(plot_id):
        return str(plot_id).split(":", 2)

    def hide(self):
        self.render_geo_pos_selector = False

    def destroy(self):
        if self.destroyed:
            return
        self.plants.clear()
        self.plant_info = None
        self.geo_pos = None
        super().destroy()
