import math
import sqlite3
import threading
import zlib

import numpy as np
from _distutils_hack import override

from repository.map_tiles.map_tile_repository import MapTileRepository
from util.data_texture_util import bilinear_sample_area
from util.paths import HEIGHT_TILES_DB_PATH


class GebcoTileRepository(MapTileRepository):
    def __init__(self):
        self.db_path = f"file:{HEIGHT_TILES_DB_PATH}?mode=ro"
        self.target_tile_size = 64

        # Thread-local storage isolates connections per background thread
        self.local_storage = threading.local()

    @property
    def data_resolution(self) -> int:
        return self.target_tile_size

    @property
    def data_format(self) -> np.dtype:
        return np.int16

    def _get_thread_cursor(self):
        if not hasattr(self.local_storage, "conn"):
            # Open a dedicated connection for this specific thread
            self.local_storage.conn = sqlite3.connect(self.db_path, uri=True, check_same_thread=False)
            self.local_storage.cursor = self.local_storage.conn.cursor()
        return self.local_storage.cursor

    def _raw_fetch(self, column, row, level):
        try:
            cursor = self._get_thread_cursor()
            cursor.execute("SELECT data FROM tiles WHERE z=? AND x=? AND y=?", (level, column, row))
            fetched_row = cursor.fetchone()

            if fetched_row is None or fetched_row[0] is None:
                return None

            decompressed = zlib.decompress(fetched_row[0])
            flat_array = np.frombuffer(decompressed, dtype=np.int16)

            stored_side = int(math.sqrt(len(flat_array)))
            tile = flat_array.reshape(stored_side, stored_side)

            if stored_side != self.target_tile_size:
                row_indices = np.linspace(0, stored_side - 1, self.target_tile_size).astype(int)
                col_indices = np.linspace(0, stored_side - 1, self.target_tile_size).astype(int)
                tile = tile[np.ix_(row_indices, col_indices)]

            return tile

        except Exception:
            return None

    def get_data(self, column, row, level) -> np.ndarray:
        tile_data = self._raw_fetch(column, row, level)
        if tile_data is not None:
            return tile_data

        for target_z in range(level - 1, -1, -1):
            d = level - target_z
            ancestor_x = column >> d
            ancestor_y = row >> d

            ancestor_tile = self._raw_fetch(ancestor_x, ancestor_y, target_z)
            if ancestor_tile is not None:
                dx = column % (2 ** d)
                dy = row % (2 ** d)

                stored_side = ancestor_tile.shape[0]
                stride = stored_side / (2 ** d)
                ys = (dy + np.arange(self.target_tile_size) / self.target_tile_size) * stride
                xs = (dx + np.arange(self.target_tile_size) / self.target_tile_size) * stride

                return bilinear_sample_area(ancestor_tile, ys, xs)

        return np.zeros((self.target_tile_size, self.target_tile_size), dtype=np.int16)

    def close(self):
        if hasattr(self.local_storage, "conn"):
            self.local_storage.conn.close()
