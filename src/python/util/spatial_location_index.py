import numpy as np
from scipy.spatial import cKDTree

from model.geo_pos import GeoPos
from util.geo_projection import project_to_globe


class SpatialLocationIndex:
    def __init__(self, locations: list[GeoPos]):
        self.locations = locations
        self.tree = cKDTree(np.array([project_to_globe(p) for p in locations]))

    def get_closest(self, query_pos: GeoPos, max_radius_m=50_000):
        target_xyz = project_to_globe(query_pos)
        dist, index = self.tree.query(target_xyz, distance_upper_bound=max_radius_m)

        if index < len(self.locations):
            return self.locations[index]
        else:
            return None
