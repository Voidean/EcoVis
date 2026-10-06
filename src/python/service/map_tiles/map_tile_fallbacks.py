import math

import numpy as np
from OpenGL.GL import *

from model.map_tiles.quad_tree import children
from rendering.data.shader_buffer import ShaderBuffer
from rendering.shaders.compute_shader import ComputeShader
from service.map_tiles.map_tile_cache import MapTileCache

SPLIT_JOB_DTYPE = np.dtype([
    ('dest_layer', np.int32), ('src_layer', np.int32),
    ('uv_scale', np.float32), ('pad', np.int32),
    ('uv_offset', np.float32, 2), ('pad2', np.float32, 2)
])

MERGE_JOB_DTYPE = np.dtype([
    ('dest_layer', np.int32),
    ('src_tl', np.int32), ('src_tr', np.int32),
    ('src_bl', np.int32), ('src_br', np.int32),
    ('pad', np.int32, 3)
])


class MapTileFallbacks:
    def __init__(self, cache: MapTileCache):
        self.cache = cache

        self.shaders = {}

        self.targets = list(self.cache.arrays.values())

    def generate_fallbacks(self, leaves):
        split_jobs = []
        merge_jobs = []

        # todo: think about if double fallback generation is prevented correctly

        for node in leaves:
            layer = self.cache.get_layer_index(node.position)
            has_any_real_data = bool(self.cache.loaded_channels.get(node.position))
            if layer is not None and has_any_real_data: continue

            if all(c in self.cache.layer_index_map for c in children(node.position)):
                src_layers = [self.cache.get_layer_index(pos) for pos in children(node.position)]
                dest_layer = self.cache.reserve_layer(node.position)

                job = np.zeros(1, dtype=MERGE_JOB_DTYPE)
                job['dest_layer'] = dest_layer
                job['src_tl'] = src_layers[0]
                job['src_tr'] = src_layers[1]
                job['src_bl'] = src_layers[2]
                job['src_br'] = src_layers[3]
                merge_jobs.append(job)

            elif layer is None:
                src_layer, level_diff = self.cache.get_closest_ancestor_layer(node.position)
                dest_layer = self.cache.reserve_layer(node.position)

                scale = 1.0 / (2 ** level_diff)
                local_x = node.column - ((node.column >> level_diff) << level_diff)
                local_y = node.row - ((node.row >> level_diff) << level_diff)

                job = np.zeros(1, dtype=SPLIT_JOB_DTYPE)
                job['dest_layer'] = dest_layer
                job['src_layer'] = src_layer
                job['uv_scale'] = scale
                job['uv_offset'] = (local_x * scale, local_y * scale)
                split_jobs.append(job)

        if split_jobs:
            split_data = np.concatenate(split_jobs)
            self._dispatch("MapTileSplit", split_data)

        if merge_jobs:
            merge_data = np.concatenate(merge_jobs)
            self._dispatch("MapTileMerge", merge_data)

        if split_jobs or merge_jobs:
            glMemoryBarrier(GL_TEXTURE_FETCH_BARRIER_BIT | GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

    def _dispatch(self, shader_name, data):
        ssbo = ShaderBuffer(data, usage=GL_STREAM_DRAW)

        for texture in self.targets:
            shader = self.get_shader(shader_name, texture)

            gx, gy = math.ceil(texture.width / 16.0), math.ceil(texture.height / 16.0)

            ssbo.bind(0)
            shader.use()
            texture.use(texture_unit=0)
            shader.set_int("sourceArray", 0)
            texture.bind_image(1, access=GL_WRITE_ONLY)
            shader.dispatch(gx, gy, len(data))

        ssbo.delete()

    def get_shader(self, shader_name, texture):
        key = (shader_name, texture.glsl_format)
        if key in self.shaders:
            return self.shaders[key]
        else:
            shader = ComputeShader(shader_name, defines={"FORMAT_QUALIFIER": texture.glsl_format})
            self.shaders[key] = shader
            return shader
