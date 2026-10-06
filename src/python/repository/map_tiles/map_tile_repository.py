from abc import ABC, abstractmethod
import numpy as np

class MapTileRepository(ABC):
    @property
    @abstractmethod
    def data_resolution(self) -> int:
        pass

    @property
    @abstractmethod
    def data_format(self) -> np.dtype:
        pass

    @abstractmethod
    async def get_data(self, column, row, level) -> np.ndarray | None:
        pass
