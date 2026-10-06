from abc import ABC


class SyncViewModel(ABC):
    """Host/link synchronization state without rendering dependencies."""

    def __init__(self):
        self.links: list[SyncViewModel] = []
        self.host: SyncViewModel | None = None
        self.sync_mode = "None"
        self.sync_options = ["None"]

    def set_sync_host(self, other: "SyncViewModel"):
        if other is self or other in self.links:
            return
        other.desync()
        self.links.append(other)
        other.host = self
        other.sync()

    def update_links(self):
        for link in list(self.links):
            link.sync()

    def sync(self):
        """Copy the configured state from ``host`` in concrete view models."""

    def destroy_sync(self):
        self.desync()
        self.desync_others()
        if get_current_host_search() is self:
            set_current_host_search(None)

    def desync(self):
        if self.host:
            if self in self.host.links:
                self.host.links.remove(self)
            self.host = None

    def desync_others(self):
        for link in list(self.links):
            link.host = None
        self.links.clear()


_current_host_search: SyncViewModel | None = None


def get_current_host_search() -> SyncViewModel | None:
    return _current_host_search


def set_current_host_search(value: SyncViewModel | None):
    global _current_host_search
    _current_host_search = value
