from dataclasses import dataclass

import numpy as np

from provider import elevation_map_tile_repository, diffuse_map_tile_repository
from repository.map_tiles.map_tile_repository import MapTileRepository


@dataclass
class TileChannel:
    identifier: str
    resolution: int
    channels: int
    dtype: np.dtype
    repository: MapTileRepository | None
    priority_offset: int = 0

    def __eq__(self, other):
        if not isinstance(other, TileChannel): return NotImplemented
        return self.identifier == other.identifier

    def __hash__(self):
        return hash(self.identifier)


diffuse_channel = TileChannel(
    identifier="diffuse",
    resolution=diffuse_map_tile_repository().data_resolution,
    channels=4,
    dtype=diffuse_map_tile_repository().data_format,
    repository=diffuse_map_tile_repository(),
    priority_offset=2

)
heightmap_channel = TileChannel(
    identifier="heightmap",
    resolution=elevation_map_tile_repository().data_resolution,
    channels=1,
    dtype=elevation_map_tile_repository().data_format,
    repository=elevation_map_tile_repository(),
)
normal_map_channel = TileChannel(
    identifier="normalMap",
    resolution=elevation_map_tile_repository().data_resolution,
    channels=4,
    dtype=np.uint8,
    repository=None,
)

tile_channels = [diffuse_channel, heightmap_channel, normal_map_channel]

streamed_channels = [diffuse_channel, heightmap_channel]
