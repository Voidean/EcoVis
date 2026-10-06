import numpy as np

from repository.map_tiles.mapbox_elevation_tile_repository import MapboxElevationTileRepository


class MapzenElevationTileRepository(MapboxElevationTileRepository):
    @staticmethod
    def decode_elevation(rgb: np.ndarray) -> np.ndarray:
        rgb_3ch = rgb[..., :3]

        r = rgb_3ch[..., 0].astype(np.float32)
        g = rgb_3ch[..., 1].astype(np.float32)
        b = rgb_3ch[..., 2].astype(np.float32)

        return r * 256.0 + g + b / 256.0 - 32768.0
