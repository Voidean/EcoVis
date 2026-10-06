import logging

from PIL import Image

from model.data_requests import WindroseRequest
from model.geo_pos import GeoPos
from service.data_streamer import AsyncDataLoader
from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from util.windrose_image import create_windrose_image


logger = logging.getLogger(__name__)


def load_windrose(request: WindroseRequest) -> Image.Image | None:
    return create_windrose_image(
        request.location,
        request.start_date,
        request.end_date,
    )


class WindroseViewModel(GraphDisplayViewModel):
    """Windrose representation of a weather graph's location and time range."""

    display_name = "Windrose"
    uses_time_axis = False
    merge_supported = False

    def __init__(self, source):
        super().__init__(source)
        self.error: str | None = None
        self._loading = False
        self._pending_image: Image.Image | None = None
        self._request: WindroseRequest | None = None
        self._image_loader = AsyncDataLoader[WindroseRequest, Image.Image | None](
            load_windrose,
            thread_name_prefix="WindroseData",
        )

    def tick(self):
        if self.destroyed:
            return
        self._poll_image()
        geo_pos: GeoPos | None = self.source.geo_pos
        if geo_pos is None:
            return
        start_time = getattr(
            self.source,
            "applied_start_time",
            self.source.start_time,
        )
        end_time = getattr(
            self.source,
            "applied_end_time",
            self.source.end_time,
        )
        request = WindroseRequest(
            location=geo_pos,
            start_date=start_time,
            end_date=end_time,
        )
        if request != self._request:
            self._request = request
            self._request_image(request)

    def take_pending_image(self) -> Image.Image | None:
        image = self._pending_image
        self._pending_image = None
        return image

    @property
    def loading(self) -> bool:
        return self._loading

    def _request_image(self, request: WindroseRequest):
        self._image_loader.submit(request)
        self._loading = True
        self.error = None

    def _poll_image(self):
        outcome = self._image_loader.update()
        if outcome is None:
            return
        self._loading = False
        if outcome.error is not None:
            logger.warning("Failed to generate windrose image: %s", outcome.error)
            self.error = "Unable to load windrose."
            self._pending_image = None
            return
        if outcome.value is None:
            self.error = "Unable to load windrose."
            self._pending_image = None
            return
        self.error = None
        self._pending_image = outcome.value

    def destroy(self):
        if self.destroyed:
            return
        self._image_loader.shutdown()
        self._loading = False
        self._pending_image = None
        self._request = None
        super().destroy()
