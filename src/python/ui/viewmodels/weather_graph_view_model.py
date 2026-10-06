from dataclasses import dataclass

from model.data_requests import GraphPlotRequest, WeatherPlotRequest
from model.geo_pos import GeoPos
from provider import point_weather_repository
from repository.weather_data.point_weather_data_repository import (
    DailyType,
    HourlyType,
)
from ui.viewmodels.graph_view_model import GraphViewModel
from ui.viewmodels.plot_view_model import Plots
from ui.viewmodels.windrose_view_model import WindroseViewModel
from util.plotting_util import convert_datetime_arrays_to_plot
from util.time_util import safe_year_replace


@dataclass(frozen=True)
class WeatherPlotLoadResult:
    plots: Plots
    resolved_position: GeoPos | None
    model_name: str | None = None
    is_forecast: bool = False


class WeatherGraphViewModel(GraphViewModel):
    data_frequencies = (HourlyType, DailyType)
    visualization_modes = ("Weather series", "Windrose")

    def __init__(self):
        super().__init__()
        self.label = "Weather_data"
        self.display_name = "Weather Graph"
        self.label_y = "Temperature [°C]"
        self.data_frequency = HourlyType
        self.data_type = HourlyType.TEMPERATURE
        self.tilt = 0
        self.azimuth: int | tuple[int, ...] = 0
        self.geo_pos: GeoPos | None = None
        self.resolved_geo_pos: GeoPos | None = None
        self.render_geo_pos_selector = True
        self.render_individual_geo_pos_selector = True
        self.add_plot_view(WindroseViewModel(self))
        self.visualization_mode = "Weather series"
        self._series_plot_view = self.plot_view
        self.model_info: str | None = None

    @property
    def selectable_plot_views(self) -> list[str]:
        return list(self.plot_views)

    def set_visualization_mode(self, mode: str):
        if mode == self.visualization_mode or mode not in self.visualization_modes:
            return
        if mode == "Windrose":
            if self.plot_view != "Windrose":
                self._series_plot_view = self.plot_view
            GraphViewModel.set_plot_view(self, "Windrose")
        else:
            GraphViewModel.set_plot_view(self, self._series_plot_view)
        self.visualization_mode = mode

    def set_plot_view(self, plot_view: str):
        """Keep restored graph state consistent with the visualization mode."""
        if plot_view == "Windrose":
            self.set_visualization_mode("Windrose")
            return
        if plot_view in self.selectable_plot_views:
            self._series_plot_view = plot_view
            self.visualization_mode = "Weather series"
        super().set_plot_view(plot_view)

    def update(
            self,
            geo_pos=None,
            data_frequency=None,
            data_type=None,
            visualization_mode=None,
            tilt=None,
            azimuth=None,
            **kwargs,
    ):
        if geo_pos is not None and geo_pos != self.geo_pos:
            self.geo_pos = geo_pos
            self.changed = True
        if data_frequency is not None:
            self.set_data_frequency(data_frequency)
        if data_type is not None:
            self.set_data_type(data_type)
        if visualization_mode is not None:
            self.set_visualization_mode(visualization_mode)
        if tilt is not None:
            self.set_tilt(tilt)
        if azimuth is not None:
            self.set_azimuth(azimuth)
        super().update(**kwargs)

    def sync(self):
        from ui.viewmodels.power_graph_view_model import PowerPlantGraphViewModel

        if isinstance(self.host, WeatherGraphViewModel):
            if "Time" in self.sync_mode:
                self.start_time = self.host.start_time
                self.end_time = self.host.end_time
            if "Location" in self.sync_mode:
                self.geo_pos = self.host.geo_pos
        elif isinstance(self.host, PowerPlantGraphViewModel):
            if "Time" in self.sync_mode:
                self.start_time = self.host.start_time
                self.end_time = self.host.end_time
            if "Location" in self.sync_mode:
                if self.host.plant_info:
                    self.tilt = self.host.plant_info.neigung or 0
                    self.azimuth = self.host.plant_info.ausrichtung or (0,)
                    self.geo_pos = self.host.plant_info.pos
                else:
                    self.tilt = 0
                    self.azimuth = 0
                    self.geo_pos = None
        self.changed = True

    def set_data_frequency(self, data_frequency):
        if data_frequency is self.data_frequency:
            return
        self.data_frequency = data_frequency
        if not isinstance(self.data_type, data_frequency):
            self.data_type = list(data_frequency)[0]
        self._update_date_precision()
        self.changed = True

    def set_data_type(self, data_type):
        if data_type == self.data_type:
            return
        self.data_type = data_type
        self._update_date_precision()
        self.changed = True

    @property
    def requires_orientation(self) -> bool:
        return self.data_type == HourlyType.GLOBAL_TILTED_IRRADIANCE

    def set_tilt(self, tilt: int, *, reload: bool = True):
        tilt = min(max(tilt, 0), 90)
        if tilt != self.tilt:
            self.tilt = tilt
            if reload:
                self.changed = True

    def set_azimuth(self, azimuth: int, *, reload: bool = True):
        azimuth = min(max(azimuth, -180), 180)
        if azimuth != self.azimuth:
            self.azimuth = azimuth
            if reload:
                self.changed = True

    @property
    def location_synced_to_plant(self) -> bool:
        from ui.viewmodels.power_graph_view_model import PowerPlantGraphViewModel

        return (
            isinstance(self.host, PowerPlantGraphViewModel)
            and "Location" in self.sync_mode
        )

    def reload_plot(self):
        self.model_info = None
        if not self.geo_pos:
            self.resolved_geo_pos = None
            self._plot_loader.cancel()
            self.loading = False
            self.set_plots({})
            return
        self.resolved_geo_pos = None
        self.label_y = f"{self.data_type.display_name} [{self.data_type.unit}]"
        self._submit_plot_load(WeatherPlotRequest(
            geo_pos=self.geo_pos,
            start_time=self.start_time,
            end_time=self.end_time,
            years_prior=self.years_prior,
            data_type=self.data_type,
            tilt=self.tilt,
            azimuth=self.azimuth,
        ))

    @staticmethod
    def _load_weather_plots(request: WeatherPlotRequest) -> WeatherPlotLoadResult:
        plot_data = {}
        resolved_position = None
        model_name = None
        is_forecast = False
        for year_offset in range(request.years_prior + 1):
            plot_start = safe_year_replace(
                request.start_time,
                request.start_time.year - year_offset,
            )
            plot_end = safe_year_replace(
                request.end_time,
                request.end_time.year - year_offset,
            )
            result = point_weather_repository().fetch_data(
                request.geo_pos.lat_deg,
                request.geo_pos.lon_deg,
                request.data_type,
                plot_start,
                plot_end,
                request.tilt,
                request.azimuth,
            )
            if result and resolved_position is None:
                resolved_position = result.position
                model_name = result.model_name
                is_forecast = result.is_forecast
            if result and result.values.size:
                year_label = (
                    str(plot_start.year)
                    if plot_start.year == plot_end.year
                    else f"{plot_start.year}–{plot_end.year}"
                )
                timestamps = [
                    safe_year_replace(timestamp, timestamp.year + year_offset)
                    for timestamp in result.timestamps
                ]
                plot_data[year_label] = convert_datetime_arrays_to_plot(
                    timestamps,
                    result.values,
                )
        return WeatherPlotLoadResult(
            plot_data,
            resolved_position,
            model_name,
            is_forecast,
        )

    def _load_plot_request(self, request: GraphPlotRequest) -> WeatherPlotLoadResult:
        if not isinstance(request, WeatherPlotRequest):
            raise TypeError("Weather graph received a non-weather request")
        return self._load_weather_plots(request)

    def _apply_plot_load_result(self, result):
        if not isinstance(result, WeatherPlotLoadResult):
            self.resolved_geo_pos = None
            self.model_info = None
            super()._apply_plot_load_result(result)
            return
        self.resolved_geo_pos = result.resolved_position
        model_info = None
        if result.model_name:
            model_info = f"OpenMeteo - {result.model_name}"
        if model_info and result.is_forecast:
            model_info += " (Forecast)"
        self.model_info = model_info
        super()._apply_plot_load_result(result.plots)

    def _refresh_derived_state(self):
        super()._refresh_derived_state()
        self.render_geo_pos_selector = (
            not self.host or "Location" not in self.sync_mode
        )
        if isinstance(self.azimuth, tuple) and not self.location_synced_to_plant:
            self.azimuth = self.azimuth[0] if self.azimuth else 0
            self.changed = True
        self._update_date_precision()

    def _update_date_precision(self):
        self.date_precision = ["Year", "Month", "Day"]
        if isinstance(self.data_type, HourlyType):
            self.date_precision.append("Hour")

    def hide(self):
        self.render_geo_pos_selector = False

    def destroy(self):
        if self.destroyed:
            return
        self.geo_pos = None
        self.resolved_geo_pos = None
        super().destroy()
