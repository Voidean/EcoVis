from io import BytesIO

import httpx
import numpy as np
from PIL import Image

from repository.map_tiles.map_tile_repository import MapTileRepository


class ApiTileRepository(MapTileRepository):
    def __init__(self, url, resolution=256):
        self.url = url
        self.resolution = resolution
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(http2=True, timeout=5.0)
        return self._client

    @property
    def data_resolution(self) -> int:
        return self.resolution

    @property
    def data_format(self) -> np.dtype:
        return np.uint8

    async def get_data(self, column, row, level) -> np.ndarray | None:
        url = self.url.format(x=column, y=row, z=level)

        response = await self.client.get(url)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGBA")
        image.load()
        return np.asarray(image)
