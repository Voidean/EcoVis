from model.map_tiles.tile_channel import normal_map_channel, heightmap_channel
from rendering.shaders.compute_shader import ComputeShader
from OpenGL.GL import *
import math

from service.map_tiles.map_tile_cache import MapTileCache


class MapTileNormalMaps:
    def __init__(self, cache: MapTileCache):
        self.cache = cache
        normal_tex = self.cache.arrays[normal_map_channel]
        self.shader = ComputeShader("GenerateNormalMap", defines={"FORMAT_QUALIFIER": normal_tex.glsl_format})

    def submit(self, inserted_tiles):
        if not inserted_tiles: return

        for pos, channel in inserted_tiles:
            if channel == heightmap_channel:
                layer = self.cache.get_layer_index(pos)
                if layer is None: continue
                self.generate(pos, layer)
                self.cache.loaded_channels[pos].add(normal_map_channel) # Mark channel active

    def generate(self, node_pos: tuple[int, int, int], layer_index: int):
        height_texture = self.cache.arrays[heightmap_channel]
        normal_texture = self.cache.arrays[normal_map_channel]

        self.shader.use()

        height_texture.use(texture_unit=0)
        self.shader.set_int("heightmap", 0)

        normal_texture.bind_image(1, access=GL_WRITE_ONLY)

        self.shader.set_ivec3("nodePos", node_pos)
        self.shader.set_int("layerIndex", layer_index)

        gx = math.ceil(normal_texture.width / 16.0)
        gy = math.ceil(normal_texture.height / 16.0)
        self.shader.dispatch(gx, gy, 1)

        glMemoryBarrier(GL_TEXTURE_FETCH_BARRIER_BIT | GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
