import numpy as np

from repository.map_tiles.map_tile_repository import MapTileRepository


class MapboxElevationTileRepository(MapTileRepository):
    def __init__(self, source_repo: MapTileRepository):
        self.source_repo = source_repo

    @property
    def data_resolution(self) -> int:
        return self.source_repo.data_resolution

    @property
    def data_format(self) -> np.dtype:
        return np.dtype(np.float32)

    @staticmethod
    def decode_elevation(rgb: np.ndarray) -> np.ndarray:
        rgb_3ch = rgb[..., :3]

        r = rgb_3ch[..., 0].astype(np.float32)
        g = rgb_3ch[..., 1].astype(np.float32)
        b = rgb_3ch[..., 2].astype(np.float32)

        return -10000.0 + (r * 65536.0 + g * 256.0 + b) * 0.1

    async def get_data(self, column, row, level) -> np.ndarray | None:
        rgb_data = await self.source_repo.get_data(column, row, level)
        if rgb_data is None: return None

        return self.decode_elevation(rgb_data)
