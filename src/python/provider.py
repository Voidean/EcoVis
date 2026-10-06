from repository.elevation_repository import OpenMeteoElevationApi, ElevationRepository
from repository.map_tiles.api_tile_repository import ApiTileRepository
from repository.map_tiles.disk_cached_tile_repository import DiskCachedTileRepository
from repository.map_tiles.map_tile_repository import MapTileRepository
from repository.map_tiles.mapbox_elevation_tile_repository import MapboxElevationTileRepository
from repository.power_data.csv_sqlite_power_metadata_repository import CSVSqlitePowerMetadataRepository
from repository.power_data.hdf5_power_repository import H5PowerTimeSeriesRepository
from repository.power_data.power_models_repository import PowerModelsRepository
from repository.power_data.power_point_repository import PowerPointRepository
from repository.power_data.power_time_series_repository import PowerTimeSeriesRepository
from repository.power_data.sqlite_power_metadata_repository import SqlitePowerMetadataRepository
# from repository.weather_data.file_weather_data_repository import FileWeatherDataRepository
from repository.weather_data.herbie_weather_data_repository import HerbieWeatherDataRepository
from repository.weather_data.open_meteo_point_weather_data_repository import OpenMeteoApi
from repository.weather_data.point_weather_data_repository import PointWeatherDataRepository
from repository.weather_data.weather_data_repository import WeatherDataRepository

#_weather_data_repository = FileWeatherDataRepository()
_weather_data_repository = HerbieWeatherDataRepository()
def map_weather_data_repository() -> WeatherDataRepository:
    return _weather_data_repository

_point_weather_data_repository = OpenMeteoApi()
def point_weather_repository() -> PointWeatherDataRepository:
    return _point_weather_data_repository

_power_timeseries_repository = H5PowerTimeSeriesRepository()
def power_timeseries_repository() -> PowerTimeSeriesRepository:
    return _power_timeseries_repository

_power_metadata_repository = CSVSqlitePowerMetadataRepository()
def power_metadata_repository() -> SqlitePowerMetadataRepository:
    return _power_metadata_repository

_power_models_repository = PowerModelsRepository(_power_metadata_repository.plant_types)
def power_models_repository():
    return _power_models_repository

_power_point_repository = PowerPointRepository()
def power_point_repository() -> PowerPointRepository:
    return _power_point_repository

_elevation_repository = OpenMeteoElevationApi()
def elevation_api() -> ElevationRepository:
    return _elevation_repository


map_elevation_api = ApiTileRepository(
    "https://terrain.reearth.land/mapbox/elevation/{z}/{x}/{y}.png", resolution=512
) # GebcoTileRepository()
elevation_disk_cache = DiskCachedTileRepository(map_elevation_api, "reearth.db")
_elevation_map_tile_repository = MapboxElevationTileRepository(elevation_disk_cache)
def elevation_map_tile_repository() -> MapTileRepository:
    return _elevation_map_tile_repository


diffuse_api = ApiTileRepository(
    # IMPORTANT TODO: REMOVE ARCGIS BEFORE PUBLISHING
    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", resolution=256
    #"https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", resolution=256
    # "https://tile.openstreetmap.org/{z}/{x}/{y}.png", resolution=256
)
_diffuse_map_tile_repository = DiskCachedTileRepository(diffuse_api, "arcgis.db")
def diffuse_map_tile_repository() -> MapTileRepository:
    return _diffuse_map_tile_repository
