from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class PowerTimeSeriesData:
    timestamps: np.ndarray
    values: np.ndarray


class PowerTimeSeriesRepository(ABC):
    @abstractmethod
    def get_value_at_timestamp(self, plant_id: int, dt: datetime, prognosis: bool = False) -> Optional[float]:
        """
        Reads the power value at a given timestamp for a given ID.
        """
        raise NotImplementedError

    @abstractmethod
    def get_values_for_range(self, plant_id: int, start_dt: datetime,
                             end_dt: datetime,
                             prognosis: bool = False) -> PowerTimeSeriesData:
        """
        Returns all measurements within a specified range for a given ID.
        """
        raise NotImplementedError
