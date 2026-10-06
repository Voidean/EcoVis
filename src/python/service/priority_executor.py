import itertools
import queue
import threading
from concurrent.futures import Executor, Future


class PriorityThreadPoolExecutor(Executor):
    def __init__(self, max_workers=4, thread_name_prefix="PriorityWorker"):
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix

        self._queue = queue.PriorityQueue()
        self._threads = []
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

        self._counter = itertools.count()

        for i in range(self.max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"{self.thread_name_prefix}-{i}",
                daemon=True
            )
            t.start()
            self._threads.append(t)

    def submit(self, fn, *args, **kwargs):
        # Standard Executor interface. Defaults to priority 0.
        return self.submit_prioritized(0, fn, *args, **kwargs)

    def submit_prioritized(self, priority, fn, *args, **kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("Cannot schedule new futures after shutdown")

            future = Future()
            task_id = next(self._counter)

            # Put the future and the work into the priority queue
            self._queue.put((priority, task_id, future, fn, args, kwargs))
            return future

    def _worker_loop(self):
        while True:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                if self._shutdown:
                    break
                else:
                    continue

            priority, task_id, future, fn, args, kwargs = item

            if not future.set_running_or_notify_cancel():
                self._queue.task_done()
                continue

            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
            except BaseException as exc:
                future.set_exception(exc)
            finally:
                self._queue.task_done()

    def shutdown(self, wait=True, cancel_futures=False):
        with self._shutdown_lock:
            self._shutdown = True

            if cancel_futures:
                while not self._queue.empty():
                    try:
                        _, _, future, _, _, _ = self._queue.get_nowait()
                        future.cancel()
                        self._queue.task_done()
                    except queue.Empty:
                        break

        if wait:
            for t in self._threads:
                t.join()
