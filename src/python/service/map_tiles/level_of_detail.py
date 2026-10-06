import logging

import numpy as np
from pyglm import glm

from model.projection import Projection
from model.state.debug_state import debug_state
from model.map_tiles.map_tile_data import MapTileData
from model.map_tiles.quad_tree import QuadTree
from rendering.data.gl_data_format import Instance
from rendering.scene.camera import Camera
from service.map_tiles.map_tile_cache import MapTileCache
from service.map_tiles.map_tile_fallbacks import MapTileFallbacks
from service.map_tiles.map_tile_normal_maps import MapTileNormalMaps
from service.map_tiles.map_tile_streamer import MapTileStreamer
from util.startup import checkpoint

MAX_LEVEL = 16
SPLIT_MULTIPLIER = 3.0
MERGE_MULTIPLIER = 3.5
UPDATE_INTERVAL = 50

logger = logging.getLogger(__name__)

class LevelOfDetail:
    def __init__(self):
        self.quad_tree = QuadTree[MapTileData](MapTileData)
        debug_state.quad_tree = self.quad_tree

        self.cache = MapTileCache()
        checkpoint()
        self.streamer = MapTileStreamer(self.cache)
        checkpoint()
        self.fallbacks = MapTileFallbacks(self.cache)
        checkpoint()
        self.normal_maps = MapTileNormalMaps(self.cache)
        checkpoint()

        self.frame_count = -1
        self.render_instances = []
        self.flat_tree = np.array([], dtype=np.int32)

        self.cache.reserve_layer(self.quad_tree.root.position)

    def update(self, camera: Camera, projection: Projection) -> bool:
        inserted_tiles = self.streamer.update()

        self.normal_maps.submit(inserted_tiles)

        geometry_changed = self.update_geometry(camera, projection)

        if geometry_changed:
            self.frame_count = -(UPDATE_INTERVAL // 5) # reschedule next update sooner

            leaves = list(self.quad_tree.leaves())

            self.fallbacks.generate_fallbacks(leaves)

            self.streamer.visible_nodes = {node.position for node in leaves}
            for node in leaves: self.streamer.request_tile(node.position)

            self._rebuild_render_data()
            return True
        else:
            return False

    def update_geometry(self, camera: Camera, projection: Projection) -> bool:
        self.frame_count = (self.frame_count + 1) % UPDATE_INTERVAL
        if self.frame_count != 0: return False

        geometry_changed = False

        for node in self.quad_tree.nodes():
            if node.is_leaf:
                node.data.update(node, projection)
                dist_sq = node.data.get_distance_sq(camera.translation)

                if dist_sq < (node.data.size * SPLIT_MULTIPLIER) ** 2 and node.level < MAX_LEVEL:
                    node.subdivide()
                    geometry_changed = True

            elif all(c.is_leaf for c in node.children):
                node.data.update(node, projection)
                dist_sq = node.data.get_distance_sq(camera.translation)

                if dist_sq >= (node.data.size * MERGE_MULTIPLIER) ** 2:
                    node.make_leaf()
                    geometry_changed = True

        return geometry_changed

    def _rebuild_render_data(self):
        flat_tree = []
        instances = []

        def traverse(node):
            current_idx = len(flat_tree)
            # SSBO node: [child0, child1, child2, child3, layerIndex, pad, pad, pad]
            tree_node = [-1, -1, -1, -1, 0, 0, 0, 0]
            flat_tree.append(tree_node)

            if node.is_leaf:
                layer = self.cache.get_layer_index(node.position)
                if layer is None:
                    layer = 0
                    logger.warning("Failed to get layer for tile %d, %d, %d", *node.position)
                tree_node[4] = layer

                instances.append(Instance(nodePosLayer=glm.ivec4(node.column, node.row, node.level, layer)))
            else:
                child_indices = []
                for child in node.children:
                    child_indices.append(traverse(child))

                tree_node[0:4] = child_indices
            return current_idx

        traverse(self.quad_tree.root)
        self.flat_tree = np.array(flat_tree, dtype=np.int32)
        self.render_instances = instances

    def shutdown(self):
        self.streamer.shutdown()
