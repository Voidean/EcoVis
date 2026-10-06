import asyncio
import itertools
import logging
import queue
import threading

from model.map_tiles.quad_tree import ROOT_POS
from model.map_tiles.tile_channel import streamed_channels
from service.map_tiles.map_tile_cache import MapTileCache
from util.data_texture_util import pad_channels

logger = logging.getLogger(__name__)


class MapTileStreamer:
    def __init__(self, cache: MapTileCache, workers=4):
        self.cache = cache
        self.max_workers = workers

        self.pending_requests = set()
        self.results_queue = queue.Queue()
        self.visible_nodes = set()

        self._counter = itertools.count()

        self._loop_ready = threading.Event()
        self.async_thread = threading.Thread(
            target=self._run_async_loop,
            daemon=True,
            name="TileStreamer"
        )
        self.async_thread.start()
        self._loop_ready.wait()

        self.get_initial_tiles()

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.request_queue = asyncio.PriorityQueue()

        self.worker_tasks = [
            self.loop.create_task(self._async_worker())
            for _ in range(self.max_workers)
        ]

        self._loop_ready.set()
        self.loop.run_forever()

    def get_initial_tiles(self):
        for channel in streamed_channels:
            # Dispatch the async coroutine to the background loop
            future = asyncio.run_coroutine_threadsafe(
                channel.repository.get_data(*ROOT_POS),
                self.loop
            )

            data = future.result(timeout=10.0)
            if data is not None:
                self.cache.insert(ROOT_POS, channel, pad_channels(data, channel.channels))

    def request_tile(self, node_pos):
        for channel in streamed_channels:
            priority = -(node_pos[2] + channel.priority_offset)
            if self.cache.has_channel(node_pos, channel): continue

            if (node_pos, channel) not in self.pending_requests:
                self.pending_requests.add((node_pos, channel))

                task_item = (priority, next(self._counter), node_pos, channel)
                asyncio.run_coroutine_threadsafe(self.request_queue.put(task_item), self.loop)

    async def _async_worker(self):
        while True:
            try:
                priority, _, node_pos, channel = await self.request_queue.get()
            except asyncio.CancelledError:
                break

            try:
                if node_pos not in self.visible_nodes: continue

                data = await channel.repository.get_data(*node_pos)

                if data is not None:
                    data = pad_channels(data, channel.channels)
                    self.results_queue.put((node_pos, channel, data))

            except Exception as e:
                logger.error("Error loading data for %s", node_pos, exc_info=True)
                self.pending_requests.discard((node_pos, channel))
            finally:
                self.request_queue.task_done()

    def update(self) -> list:
        inserted_tiles = []

        try:
            pos, channel, data = self.results_queue.get_nowait()
            self.cache.insert(pos, channel, data)
            self.pending_requests.discard((pos, channel))
            inserted_tiles.append((pos, channel))
        except queue.Empty:
            pass

        return inserted_tiles

    def shutdown(self):
        if hasattr(self, "loop") and self.loop.is_running():

            async def _shutdown():
                current_task = asyncio.current_task()
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not current_task]

                for task in tasks:
                    task.cancel()

                await asyncio.gather(*tasks, return_exceptions=True)

                self.loop.stop()

            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)
            self.async_thread.join(timeout=5.0)
