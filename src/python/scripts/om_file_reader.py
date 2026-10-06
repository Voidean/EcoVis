import os
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import fsspec
import numpy as np
import requests
from PIL import Image
from omfiles import OmFileReader

from util.paths import WEATHER, CACHE

logger = logging.getLogger(__name__)

cache_lock = threading.Lock()

class OmWeatherDataTypes(Enum):
    # Temperature
    TEMPERATURE_2M = "temperature_2m"

    # Wind at 10m
    WIND_EW_10M = "wind_u_component_10m"
    WIND_NS_10M = "wind_v_component_10m"

    # Winds at approximate heights (m)
    WIND_EW_0ASL = "wind_u_component_1000hPa"
    WIND_NS_0ASL = "wind_v_component_1000hPa"
    WIND_EW_500ASL = "wind_u_component_950hPa"
    WIND_NS_500ASL = "wind_v_component_950hPa"
    WIND_EW_750ASL = "wind_u_component_925hPa"
    WIND_NS_750ASL = "wind_v_component_925hPa"
    WIND_EW_1000ASL = "wind_u_component_900hPa"
    WIND_NS_1000ASL = "wind_v_component_900hPa"
    WIND_EW_1500ASL = "wind_u_component_850hPa"
    WIND_NS_1500ASL = "wind_v_component_850hPa"
    WIND_EW_2000ASL = "wind_u_component_800hPa"
    WIND_NS_2000ASL = "wind_v_component_800hPa"
    WIND_EW_3000ASL = "wind_u_component_700hPa"
    WIND_NS_3000ASL = "wind_v_component_700hPa"

    # Jet streams
    WIND_EW_24000M = "wind_u_component_30hPa"
    WIND_NS_24000M = "wind_v_component_30hPa"


    # Cloud cover
    CLOUD_COVER = "cloud_cover"
    CLOUD_COVER_LOW = "cloud_cover_low"
    CLOUD_COVER_MID = "cloud_cover_mid"
    CLOUD_COVER_HIGH = "cloud_cover_high"
    CONVECTIVE_CLOUD_TOP = "convective_cloud_top"
    CONVECTIVE_CLOUD_BASE = "convective_cloud_base"

    # Humidity
    RELATIVE_HUMIDITY_2M = "relative_humidity_2m"

def get_json_with_retry(
    url: str,
    *,
    retries: int = 5,
    backoff: float = 0.5,
    timeout: float = 10.0,
):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(backoff * (2 ** attempt))

METADATA = get_json_with_retry("https://map-tiles.open-meteo.com/data_spatial/dwd_icon/latest.json")


def process_timestamp_batch(job):
    """
    Fetches a DWD ICON OM file for the given datetime (UTC),
    falling back to the oldest available run if dt is older than 7 days.

    Saves an 8-bit grayscale PNG named:
        YYYYMMDDHH_temperature_2m.png
    """
    dt, data_types, cache_dir = job

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    latest_ref = datetime.fromisoformat(METADATA["reference_time"].replace("Z", "+00:00"))
    oldest_valid = latest_ref - timedelta(days=7)

    # Clamp datetime to the available range
    if dt < oldest_valid:
        dt = oldest_valid
    if dt > latest_ref:
        dt = latest_ref

    YYYY = f"{dt.year:04d}"
    MM = f"{dt.month:02d}"
    DD = f"{dt.day:02d}"
    HH = f"{dt.hour:02d}"

    # Construct the S3 OM path
    s3_uri = (
        f"s3://openmeteo/data_spatial/dwd_icon/"
        f"{YYYY}/{MM}/{DD}/{HH}00Z/"
        f"{YYYY}-{MM}-{DD}T{HH}00.om"
    )

    # Construct a unique local filename based on the S3 path
    local_filename = s3_uri.split("/")[-1]
    local_path = Path(cache_dir) / local_filename

    # Thread-safe download
    with cache_lock:
        if not local_path.exists():
            logger.info("Downloading: %s", s3_uri)
            fs = fsspec.filesystem("s3", anon=True)
            # Download to a .tmp file first and rename to avoid corruption
            tmp_path = str(local_path) + ".tmp"
            fs.get(s3_uri, tmp_path)
            os.replace(tmp_path, local_path)

    # Read the local file
    try:
        with OmFileReader(str(local_path)) as om_root:
            for data_type in data_types:
                # Read data
                temp = om_root.get_child_by_name(data_type.value).read_array((...))

                # Get your range first (ignoring NaNs)
                t_min = np.nanmin(temp)
                t_max = np.nanmax(temp)
                denom = (t_max - t_min) if t_max != t_min else 1

                # Perform the normalization (this will still have NaNs in the result)
                normalized = (255 * (temp - t_min) / denom)

                # Replace NaNs with 0 (or any floor value) before casting
                normalized = np.nan_to_num(normalized, nan=0).astype(np.uint8)

                # Flip so north is on top
                normalized = np.flipud(normalized)

                # Save texture
                ts = om_root.get_child_by_name("valid_time").read_scalar()
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)

                # Create folder for this timestamp
                folder_name = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}_{dt.hour:02d}"
                folder_path = WEATHER / folder_name
                folder_path.mkdir(parents=True, exist_ok=True)

                filename = f"{data_type.value}.png"
                Image.fromarray(normalized, mode="L").save(folder_path / filename)
                logger.info("Saved %s: %s", folder_name, filename)
    except Exception as e:
        logger.error("Error reading %s", local_path, exc_info=True)
        # delete corrupted file so next run retries
        if local_path.exists(): local_path.unlink()
        raise

    return dt


def main():
    # Create one persistent cache directory for the duration of the script
    cache_path = CACHE / "open_meteo"
    cache_path.mkdir(exist_ok=True)

    base_dt = datetime(2026, 1, 19, 12, tzinfo=timezone.utc)

    # Grouping: One job per timestamp
    jobs = []
    num_days = 8
    for i in range(4 * num_days):
        current_dt = base_dt + timedelta(hours=i * 6)
        jobs.append((current_dt, list(OmWeatherDataTypes), str(cache_path)))
    start = time.perf_counter()

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_timestamp_batch, jobs))
    finally:
        pass # shutil.rmtree(cache_path, ignore_errors=True)

    logger.info("Total time: %.2fs", time.perf_counter() - start)

if __name__ == "__main__":
    main()
