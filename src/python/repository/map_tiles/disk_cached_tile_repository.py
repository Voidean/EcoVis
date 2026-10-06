import asyncio
import logging
import sqlite3
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from repository.map_tiles.map_tile_repository import MapTileRepository
from util.paths import TILES_CACHE

logger = logging.getLogger(__name__)


class DiskCachedTileRepository(MapTileRepository):
    def __init__(self, source_repo: MapTileRepository, db_file: str, max_tiles=5_000):
        self.source_repo = source_repo
        self.db_path = TILES_CACHE / db_file
        self.max_tiles = max_tiles

        self._init_db_schema()

        self.write_queue = None
        self.writer_task = None

        self.local_storage = threading.local()
        self.read_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="TileReader")

    @property
    def data_resolution(self) -> int:
        return self.source_repo.data_resolution

    @property
    def data_format(self) -> np.dtype:
        return self.source_repo.data_format

    def _ensure_async_setup(self):
        if self.write_queue is None:
            self.write_queue = asyncio.Queue()
            self.writer_task = asyncio.create_task(self._background_writer_loop())

    def _init_db_schema(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS tiles (
                z INTEGER, x INTEGER, y INTEGER,
                last_accessed REAL,
                data BLOB,
                PRIMARY KEY (z, x, y)
            );
            CREATE INDEX IF NOT EXISTS idx_accessed ON tiles(last_accessed);
        """)
        conn.commit()
        conn.close()

    def _get_read_conn(self):
        if not hasattr(self.local_storage, "conn"):
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            self.local_storage.conn = conn
        return self.local_storage.conn

    def _fetch_from_disk(self, column, row, level):
        conn = self._get_read_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT data, last_accessed FROM tiles WHERE z=? AND x=? AND y=?", (level, column, row))
        row_data = cursor.fetchone()

        if row_data:
            data, last_accessed = row_data

            decompressed = zlib.decompress(data)
            flat_array = np.frombuffer(decompressed, dtype=self.data_format)

            channels = len(flat_array) // (self.data_resolution * self.data_resolution)
            reshaped_data = flat_array.reshape((self.data_resolution, self.data_resolution, channels))

            # Return both the data and the timestamp to the async loop
            return reshaped_data, last_accessed

        return None, None

    def _write_to_disk(self, level, column, row, api_data, enforce_lru):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()

        try:
            # If api_data is None, this is just a request to update the timestamp
            if api_data is None:
                cursor.execute(
                    "UPDATE tiles SET last_accessed=? WHERE z=? AND x=? AND y=?",
                    (time.time(), level, column, row)
                )
            else:
                compressed_data = zlib.compress(api_data.tobytes(), level=2)
                cursor.execute("""
                               INSERT INTO tiles (z, x, y, last_accessed, data)
                               VALUES (?, ?, ?, ?, ?) ON CONFLICT(z, x, y) DO
                               UPDATE SET last_accessed=excluded.last_accessed;
                               """, (level, column, row, time.time(), compressed_data))

                if enforce_lru:
                    cursor.execute("SELECT COUNT(*) FROM tiles")
                    tiles_count = cursor.fetchone()[0]
                    if tiles_count > self.max_tiles:
                        delete_count = self.max_tiles // 10
                        cursor.execute(f"""
                            DELETE FROM tiles WHERE rowid IN (
                                SELECT rowid FROM tiles ORDER BY last_accessed ASC LIMIT {delete_count}
                            )
                        """)

            conn.commit()
        finally:
            conn.close()

    async def _background_writer_loop(self):
        insert_counter = 0

        while True:
            try:
                task = await self.write_queue.get()
            except asyncio.CancelledError:
                break

            if task is None:
                self.write_queue.task_done()
                break

            try:
                level, column, row, api_data = task

                enforce_lru = False
                if api_data is not None:
                    insert_counter += 1
                    enforce_lru = insert_counter >= 100

                await asyncio.to_thread(self._write_to_disk, level, column, row, api_data, enforce_lru)

                if enforce_lru: insert_counter = 0

            except Exception as e:
                logger.error("Failed to process tile cache task", exc_info=True)
            finally:
                self.write_queue.task_done()

    async def get_data(self, column, row, level) -> np.ndarray | None:
        self._ensure_async_setup()

        loop = asyncio.get_running_loop()

        local_data, last_accessed = await loop.run_in_executor(
            self.read_pool, self._fetch_from_disk, column, row, level
        )

        if local_data is not None:
            if time.time() - last_accessed > 3600:
                self.write_queue.put_nowait((level, column, row, None))

            return local_data

        api_data = await self.source_repo.get_data(column, row, level)
        if api_data is not None:
            self.write_queue.put_nowait((level, column, row, api_data))
            return api_data

        return None
