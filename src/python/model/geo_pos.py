import math
from dataclasses import dataclass

from pyglm import glm


@dataclass
class GeoPos:
    lon: float  # radians
    lat: float  # radians
    elevation: float = 0.0  # metres

    @property
    def lon_deg(self):
        return math.degrees(self.lon)

    @property
    def lat_deg(self):
        return math.degrees(self.lat)

    def __repr__(self):
        return f"lon={self.lon_deg}, lat={self.lat_deg}"

    def __eq__(self, other):
        if not isinstance(other, GeoPos): return NotImplemented
        return self.lon == other.lon and self.lat == other.lat

    def __hash__(self):
        return hash((self.lon, self.lat))

    def __iter__(self):
        yield self.lon
        yield self.lat
        yield self.elevation

    @property
    def coords(self):
        return self.lon, self.lat

    @classmethod
    def from_degrees(cls, lon, lat, elevation=0.0):
        return cls(math.radians(lon), math.radians(lat), elevation)

    @property
    def vec3(self):
        return glm.vec3(self.lon, self.lat, self.elevation)

    @property
    def dvec3(self):
        return glm.dvec3(self.lon, self.lat, self.elevation)
