from __future__ import annotations

from abc import abstractmethod, ABC

import logging
from concurrent.futures import CancelledError, ThreadPoolExecutor, Future
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, Generic, TypeVar

if TYPE_CHECKING:
    from model.state.time_state import TimeState


logger = logging.getLogger(__name__)


RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class AsyncLoadResult(Generic[ResultT]):
    value: ResultT | None = None
    error: Exception | None = None


class AsyncDataLoader(Generic[RequestT, ResultT]):
    """Executes single-task loading requests asynchronously in a background thread.

        Submitting a new request automatically cancels pending work and supersedes older results.

        Usage:
            >>> loader = AsyncDataLoader(load_fn)
            >>> loader.submit(request_data)
            >>> # Call per frame on the main/UI thread:
            >>> if result := loader.update():
            ...     handle_data(result.value)
            >>> loader.shutdown()
    """

    def __init__(
            self,
            load: Callable[[RequestT], ResultT],
            max_workers: int = 2,
            thread_name_prefix: str = "AsyncDataLoader",
    ):
        self._load = load
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._future: Future[tuple[int, ResultT]] | None = None
        self._generation = 0
        self._shutdown = False

    def submit(self, request: RequestT) -> None:
        """Submit a request, replacing any older pending request."""
        if self._shutdown:
            raise RuntimeError("Cannot submit work after shutting down the data loader")

        self._generation += 1
        generation = self._generation
        if self._future is not None:
            self._future.cancel()

        self._future = self._executor.submit(
            lambda: (generation, self._load(request))
        )

    def update(self) -> AsyncLoadResult[ResultT] | None:
        if self._future is None or not self._future.done():
            return None

        future = self._future
        self._future = None
        try:
            generation, value = future.result()
        except CancelledError:
            return None
        except Exception as error:
            return AsyncLoadResult(error=error)

        if generation != self._generation:
            return None
        return AsyncLoadResult(value=value)

    def cancel(self) -> None:
        """Invalidate and detach the current request, if any."""
        if self._shutdown:
            return
        self._generation += 1
        if self._future is not None:
            self._future.cancel()
            self._future = None

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._generation += 1
        if self._future is not None:
            self._future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)


class DataStreamer(ABC):
    def __init__(self, time_state: TimeState):
        from provider import map_weather_data_repository

        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DataStreamer")

        self.time_state = time_state
        self.current_data_time = map_weather_data_repository().initial_time

        self.generation = 0
        self.pending: dict[datetime, Future] = dict()
        self.ready: dict[datetime, Dict] = dict()

    def update(self):
        for time in list(self.pending.keys()):
            future = self.pending[time]
            if future.done():
                del self.pending[time]
                try:
                    gen, data = future.result()
                except CancelledError:
                    continue
                except Exception:
                    logger.error("Failed to load data for %s", time, exc_info=True)
                    continue
                if gen == self.generation:
                    self.ready[time] = data

        # If current time is ready, apply it to the active textures
        for time in list(self.ready.keys()):
            if self.current_data_time == time:
                self.apply_data()
            elif self.current_data_time > time:
                del self.ready[time]  # remove data that is before the current time

    @abstractmethod
    def apply_data(self):
        pass

    @abstractmethod
    def _submit_load(self, time):
        pass

    def set_time(self, new_time: datetime):
        if new_time == self.current_data_time: return

        if not self.time_state.is_next_data_time(self.current_data_time, new_time):
            self.invalidate()  # Invalidate if it's a non-sequential jump
        self.current_data_time = new_time
        self._trigger_pipeline()

    def _trigger_pipeline(self):
        self._submit_load(self.current_data_time)
        next_time = self.time_state.next_data_time(self.current_data_time)
        if next_time: self._submit_load(next_time)

    def invalidate(self):
        self.generation += 1
        for future in self.pending.values():
            future.cancel()
        self.pending.clear()
        self.ready.clear()

    def shutdown(self):
        if self.executor is None:
            return
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.executor = None
