from collections import OrderedDict
import numpy as np

from model.map_tiles.quad_tree import ancestors, ROOT_POS
from util.config import config
from model.map_tiles.tile_channel import tile_channels
from rendering.textures.texture_array import TextureArray


class MapTileCache:
    def __init__(self):
        self.capacity = config.graphics.tile_gpu_cache_size

        self.arrays = {channel: TextureArray(
            width=channel.resolution, height=channel.resolution,
            channels=channel.channels, depth=self.capacity,
            dtype=channel.dtype,
        ) for channel in tile_channels}

        self.layer_index_map = OrderedDict()
        self.loaded_channels = {ROOT_POS: set()}
        self.free_layers = list(range(1, self.capacity))

    def reserve_layer(self, node_pos: tuple[int, int, int]) -> int:
        layer_index = self.get_layer_index(node_pos)
        if layer_index is not None: return layer_index

        if self.free_layers:
            layer_index = self.free_layers.pop()
        else:
            evicted_node, layer_index = self.layer_index_map.popitem(last=False)
            self.loaded_channels.pop(evicted_node, None)

        self.layer_index_map[node_pos] = layer_index
        if node_pos not in self.loaded_channels:
            self.loaded_channels[node_pos] = set()

        return layer_index

    def insert(self, node_pos: tuple[int, int, int], channel, data: np.ndarray) -> int:
        layer_index = self.reserve_layer(node_pos)
        self.arrays[channel].update_layer(layer_index, data)
        self.loaded_channels[node_pos].add(channel)
        return layer_index

    def get_layer_index(self, node_pos: tuple[int, int, int]) -> int | None:
        if node_pos in self.layer_index_map:
            self.layer_index_map.move_to_end(node_pos)
            return self.layer_index_map[node_pos]
        elif node_pos == ROOT_POS: return 0
        else: return None

    def has_channel(self, node_pos: tuple[int, int, int], channel) -> bool:
        return node_pos in self.loaded_channels and channel in self.loaded_channels[node_pos]

    def get_closest_ancestor_layer(self, node_pos: tuple[int, int, int]) -> tuple[int, int] | None:
        """Finds the closest ancestor that currently occupies a layer (real or fallback)."""
        for ancestor_pos, level_delta in ancestors(node_pos):
            layer_index = self.get_layer_index(ancestor_pos)
            if layer_index is not None: return layer_index, level_delta
        raise AssertionError
