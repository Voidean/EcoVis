from abc import ABC, abstractmethod
from typing import List, Tuple, Union, Iterable, Optional

import requests

from model.geo_pos import GeoPos


class ElevationRepository(ABC):
    def __init__(self, batch_size: int = 100, timeout: int = 10):
        """
        :param batch_size: Number of coordinates per HTTP request (max. ~500 recommended due to URL length limits).
        :param timeout: Timeout for the HTTP request in seconds.
        """
        self.batch_size = batch_size
        self.timeout = timeout
        self.session = requests.Session()

    @abstractmethod
    def get_elevation(self, location: Union[Tuple[float, float], GeoPos, float], lon: Optional[float] = None) -> GeoPos:
        raise NotImplementedError

    @abstractmethod
    def get_elevations(self, locations: Iterable[Union[Tuple[float, float], GeoPos]]) -> List[GeoPos]:
        raise NotImplementedError

    def close(self):
        self.session.close()

class OpenMeteoElevationApi(ElevationRepository):
    """
    Client for the free Open-Meteo Elevation API.
    Supports automatic chunking for batch requests as well as querying single points.
    """
    BASE_URL = "https://api.open-meteo.com/v1/elevation"

    def get_elevation(self, location: Union[Tuple[float, float], GeoPos, float], lon: Optional[float] = None) -> GeoPos:
        """
        Fetches the elevation for a single location.

        Can be called in various ways:
          - api.get_elevation((lat, lon))
          - api.get_elevation(geo_pos_instance)
          - api.get_elevation(lat, lon)

        :param location: (lat_deg, lon_deg) tuple, GeoPos instance, OR lat_deg as float.
        :param lon: Optional lon_deg as float (if location is passed as a lat_deg float).
        :return: GeoPos instance with the elevation value set.
        """
        if isinstance(location, (int, float)) and lon is not None:
            loc_input = (float(location), float(lon))
        else:
            loc_input = location

        results = self.get_elevations([loc_input])
        if not results:
            raise RuntimeError("Elevation fetch failed for the specified location.")

        return results[0]

    def get_elevations(self, locations: Iterable[Union[Tuple[float, float], GeoPos]]) -> List[GeoPos]:
        """
        Accepts a list of (lat, lon) tuples in degrees OR existing GeoPos objects,
        and returns a list of GeoPos objects including the fetched elevation.

        :param locations: List of (lat_deg, lon_deg) tuples OR GeoPos instances.
        :return: List of GeoPos instances with set elevation values.
        """
        # Standardize format: List of (lat_deg, lon_deg)
        coords_deg: List[Tuple[float, float]] = []
        for loc in locations:
            if isinstance(loc, GeoPos):
                coords_deg.append((loc.lat_deg, loc.lon_deg))
            elif isinstance(loc, (tuple, list)) and len(loc) >= 2:
                coords_deg.append((float(loc[0]), float(loc[1])))
            else:
                raise ValueError(f"Invalid data format for location: {loc}")

        if not coords_deg:
            return []

        results: List[GeoPos] = []

        # Split into chunks to avoid exceeding the URL length limit
        for i in range(0, len(coords_deg), self.batch_size):
            chunk = coords_deg[i: i + self.batch_size]

            lats = [str(lat) for lat, _ in chunk]
            lons = [str(lon) for _, lon in chunk]

            params = {
                "latitude": ",".join(lats),
                "longitude": ",".join(lons)
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            elevations = data.get("elevation", [])

            if len(elevations) != len(chunk):
                raise RuntimeError(
                    f"API returned {len(elevations)} elevation values, but {len(chunk)} were requested."
                )

            # Construct GeoPos objects (Note: from_degrees expects lon, lat, elevation)
            for (lat, lon), elev in zip(chunk, elevations):
                # If the API returns null (e.g. for errors over oceans), default to 0.0
                valid_elev = float(elev) if elev is not None else 0.0
                results.append(GeoPos.from_degrees(lon=lon, lat=lat, elevation=valid_elev))
        return results
