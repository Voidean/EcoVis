import logging
import sqlite3
import math
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.crs import CRS

from util.paths import HEIGHT_TILES_DB_PATH, NC_FILE

logger = logging.getLogger(__name__)

# Configuration
TILE_SIZE = 256  # Fixed array dimension
MAX_EQUATOR_ZOOM = 9  # Zoom 9 is ~305m at equator, matching 464m data well


def get_max_zoom_for_lat(lat_deg):
    """Calculates the maximum useful zoom level for a given latitude."""
    lat_rad = math.radians(abs(lat_deg))
    val = 337.37 * math.cos(lat_rad)
    if val <= 1:
        return 0
    return min(MAX_EQUATOR_ZOOM, int(math.log2(val)))


def tile_to_bounds_3857(x, y, z):
    """Returns the EPSG:3857 bounding box for a given slippy map tile."""
    MAX_EXTENT = 20037508.342789244
    res = (MAX_EXTENT * 2) / (2 ** z)
    minx = -MAX_EXTENT + x * res
    maxx = minx + res
    maxy = MAX_EXTENT - y * res
    miny = maxy - res
    return minx, miny, maxx, maxy


def tile_to_lat_4326(y, z):
    """Returns the approximate latitude of the tile center."""
    n = math.pi - 2.0 * math.pi * (y + 0.5) / (2.0 ** z)
    return math.degrees(math.atan(math.sinh(n)))


def preconvert_gebco():
    # Initialize SQLite Database
    conn = sqlite3.connect(HEIGHT_TILES_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS tiles (z INTEGER, x INTEGER, y INTEGER, data BLOB, PRIMARY KEY (z, x, y))"
    )
    conn.commit()

    import zlib  # Native, fast, and built-in

    with rasterio.open(NC_FILE) as src:
        for z in range(MAX_EQUATOR_ZOOM + 1):
            num_tiles = 2 ** z
            logger.info("Processing zoom level %s", z)

            for x in range(num_tiles):
                for y in range(num_tiles):
                    # Check latitude limit for this tile
                    lat = tile_to_lat_4326(y, z)
                    if z > get_max_zoom_for_lat(lat):
                        continue  # Skip oversampling high-latitude zones

                    # Get EPSG:3857 bounding box for the tile
                    minx, miny, maxx, maxy = tile_to_bounds_3857(x, y, z)
                    dst_transform = rasterio.transform.from_bounds(
                        minx, miny, maxx, maxy, TILE_SIZE, TILE_SIZE
                    )

                    # Allocate destination array
                    tile_data = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.int16)

                    # Reproject from GEBCO native CRS into the tile window
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=tile_data,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=CRS.from_epsg(3857),
                        resampling=Resampling.bilinear
                    )

                    # Compress raw bytes
                    compressed_blob = zlib.compress(tile_data.tobytes(), level=6)

                    cursor.execute(
                        "INSERT OR REPLACE INTO tiles (z, x, y, data) VALUES (?, ?, ?, ?)",
                        (z, x, y, compressed_blob)
                    )
                conn.commit()  # Commit per row block / zoom level

    # Optimize database for reading
    cursor.execute("VACUUM")
    conn.close()
    logger.info("Database built successfully")


if __name__ == "__main__":
    preconvert_gebco()
