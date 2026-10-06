import logging

import netCDF4 as nc
import numpy as np
from PIL import Image
from util.paths import TEXTURES, NC_FILE

from util.coordinate_constants import MIN_ELEVATION, MAX_ELEVATION
from util.data_texture_util import scale

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURATION
# ==========================================

OUTPUT_PNG = TEXTURES / "globe" / "heightmap.png"

# Downsample factor
DOWNSAMPLE = 8

# Chunk size for streaming (rows per read)
CHUNK_ROWS = 512


# ==========================================


def normalize_chunk(chunk, global_min, global_max):
    """Normalize chunk to 0–255 uint8."""
    chunk = np.clip(chunk, global_min, global_max)
    chunk = scale(chunk, global_min, global_max)
    return (chunk * 255).astype(np.uint8)


def main():
    logger.info("Opening NetCDF")
    dataset = nc.Dataset(NC_FILE, "r")

    elev = dataset["elevation"]
    elev = np.flipud(elev)

    lat_size, lon_size = elev.shape  # 43200 × 86400

    logger.info("Original resolution: %s × %s", lon_size, lat_size)

    out_h = lat_size // DOWNSAMPLE
    out_w = lon_size // DOWNSAMPLE

    logger.info("Output resolution: %s × %s", out_w, out_h)

    # Empty output array
    output = np.zeros((out_h, out_w), dtype=np.uint8)

    out_row = 0

    logger.info("Processing in chunks")
    for start_row in range(0, lat_size, CHUNK_ROWS):
        end_row = min(start_row + CHUNK_ROWS, lat_size)

        logger.info("Loading rows %s..%s", start_row, end_row - 1)

        # Load chunk (int16)
        chunk = elev[start_row:end_row, :]

        # Downsample chunk vertically
        chunk = chunk[::DOWNSAMPLE, :]

        if chunk.size == 0:
            continue

        # Downsample horizontally
        chunk = chunk[:, ::DOWNSAMPLE]

        # Normalize
        chunk = normalize_chunk(chunk, MIN_ELEVATION, MAX_ELEVATION)

        # Store into output buffer
        rows = chunk.shape[0]
        output[out_row:out_row + rows, :] = chunk
        out_row += rows

    logger.info("Finished loading and processing; saving PNG")

    img = Image.fromarray(output, mode="L")
    img.save(OUTPUT_PNG)

    logger.info("PNG generation complete")
    logger.info("Saved: %s", OUTPUT_PNG)


if __name__ == "__main__":
    main()
