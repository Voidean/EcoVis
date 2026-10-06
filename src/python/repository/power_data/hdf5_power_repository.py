import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from repository.power_data.power_time_series_repository import (
    PowerTimeSeriesData,
    PowerTimeSeriesRepository,
)
from util.logging_config import configure_logging
from util.paths import POWER
from util.time_util import TIME_FORMAT_DISPLAY

logger = logging.getLogger(__name__)

class H5PowerTimeSeriesRepository(PowerTimeSeriesRepository):
    def __init__(self):
        self.h5_path = POWER / "powerplants_measurements.h5"
        self.h5_prognosis_path = POWER / "powerplants_prognoses.h5"

    def _get_group_key(self, malo_id: int) -> str:
        return f"malo_id_{malo_id}"

    # TODO fix!
    def get_value_at_timestamp(self, plant_id: int, dt: datetime, prognosis: bool = False) -> Optional[float]:
        """
        Reads the power value at a given timestamp for a givenD.
        """
        key = self._get_group_key(plant_id)

        target_epoch = int(dt.timestamp())

        path = self.h5_prognosis_path if prognosis else self.h5_path
        try:
            with pd.HDFStore(path, mode='r') as store:
                if key not in store:
                    logger.warning("No data for %s", plant_id)
                    return None

                df = store[key]

                if 'timestamp' not in df.columns or 'value' not in df.columns:
                    raise KeyError()

                idx = (df['timestamp'] - target_epoch).abs().idxmin()
                row = df.loc[idx]

                return float(row['value'])

        except (FileNotFoundError, KeyError, ValueError) as e:
            logger.error("Failed to load power data", exc_info=True)
            return None

    def get_values_for_range(self, plant_id: int, start_dt: datetime,
                             end_dt: datetime,
                             prognosis: bool = False) -> PowerTimeSeriesData:
        """
        Returns all measurements within a specified range for a given ID.
        """
        key = self._get_group_key(plant_id)

        path = self.h5_prognosis_path if prognosis else self.h5_path
        try:
            with pd.HDFStore(path, mode='r') as store:
                if key not in store:
                    return PowerTimeSeriesData(
                        np.array([], dtype=object),
                        np.array([], dtype=np.float64),
                    )

                df = store[key]

                clamped = df.loc[start_dt.strftime(TIME_FORMAT_DISPLAY):end_dt.strftime(TIME_FORMAT_DISPLAY)]

                series_data = clamped['Value']
                return PowerTimeSeriesData(
                    series_data.index.to_pydatetime(),
                    series_data.to_numpy(dtype=np.float64),
                )

        except (FileNotFoundError, KeyError) as e:
            logger.error("Error loading power timespan data", exc_info=True)
            return PowerTimeSeriesData(
                np.array([], dtype=object),
                np.array([], dtype=np.float64),
            )



def generate_h5_testdata(
        h5_filename: str = POWER / "powerplants_measurements.h5",
        prognosis_h5_filename: str = POWER / "powerplants_prognoses.h5"
):
    from provider import power_metadata_repository
    repo = power_metadata_repository()
    plants = repo.get_all_plants()
    # Configure Params
    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    time_step_minutes = 15
    num_points = 4 * 24 * 200

    logger.info("Generating H5 measurement test data in %s", h5_filename)
    logger.info("Generating H5 prognosis test data in %s", prognosis_h5_filename)
    logger.info("Start: %s | Interval: %s min | Points: %s", start_dt, time_step_minutes, num_points)

    with (
            pd.HDFStore(h5_filename, mode='w') as measurement_store,
            pd.HDFStore(prognosis_h5_filename, mode='w') as prognosis_store
    ):
        for plant in plants:
            # Generate actual datetime objects for the index
            timestamps = [
                start_dt + timedelta(minutes=time_step_minutes * p)
                for p in range(num_points)
            ]

            values = []

            for p in range(num_points):
                val = 0.0
                current_time = timestamps[p]
                hour = current_time.hour + current_time.minute / 60.0

                # model different producers pseudo realistic
                if plant.energietraeger == "PV":
                    if 6 <= hour <= 18:
                        solar_factor = np.sin(np.pi * (hour - 6) / 12)
                        cloud_noise = np.random.uniform(0.6, 1.0)
                        val = plant.leistung_kw * solar_factor * cloud_noise
                    else:
                        val = 0.0

                elif plant.energietraeger == "wind":
                    slow_trend = np.sin(2 * np.pi * p / 96) * 0.3 + 0.5  # 96 Punkte = 1 Tag
                    gust_noise = np.random.uniform(0.0, 0.4)
                    val = plant.leistung_kw * (slow_trend + gust_noise)
                    val = max(0.0, min(val, plant.leistung_kw))

                elif plant.energietraeger == "Biomasse":
                    val = plant.leistung_kw * np.random.uniform(0.85, 0.98)

                else:
                    val = plant.leistung_kw * (0.75 + np.sin(2 * np.pi * p / (96 * 3)) * 0.08)

                values.append(round(val, 2))

            # Prognoses follow the measurements closely. The smoothed error avoids
            # completely independent noise between adjacent forecast values.
            prognosis_error = np.random.normal(0.0, 0.05, num_points)
            prognosis_error = np.convolve(
                prognosis_error, np.ones(5) / 5, mode='same'
            )
            prognosis_bias = np.random.uniform(-0.03, 0.03)
            prognosis_values = [
                round(max(0.0, value * (1.0 + prognosis_bias + error)), 2)
                for value, error in zip(values, prognosis_error)
            ]

            # Create DataFrames with DatetimeIndex and Capitalized 'Value' Column
            measurement_df = pd.DataFrame({
                'Value': values
            }, index=pd.DatetimeIndex(timestamps, name='timestamp'))
            prognosis_df = pd.DataFrame({
                'Value': prognosis_values
            }, index=pd.DatetimeIndex(timestamps, name='timestamp'))

            group_key = f"malo_id_{plant.plant_id}"
            measurement_store.put(group_key, measurement_df, format='table')
            prognosis_store.put(group_key, prognosis_df, format='table')

    logger.info("H5 test data generation complete: %s power plants saved", len(plants))


if __name__ == "__main__":
    configure_logging(logging.INFO)
    generate_h5_testdata()
