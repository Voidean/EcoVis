import logging
import sys
from pathlib import Path
import os
import shutil

logger = logging.getLogger(__name__)

def list_filenames(folder_path):
    path = Path(folder_path)

    if path.is_dir():
        return [file.name for file in path.iterdir() if file.is_file()]
    else:
        logger.warning("%s is not a directory", folder_path)
        return []

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]

EXTERNAL_DATA = PROJECT_ROOT / "data"
RESOURCES = PROJECT_ROOT / "resources"
TEXTURES = RESOURCES / "textures"
SHADERS = RESOURCES / "shaders"
MODELS = RESOURCES / "models"
DATA = RESOURCES / "data"
WEATHER = DATA / "weather"
BORDERS = DATA / "borders"
OSM = DATA / "open_street_map"
POWER = DATA / "power_data"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "default_config.json"
CONFIG_PATH = PROJECT_ROOT / "config.json"
IMGUI_INI = str(PROJECT_ROOT / "imgui.ini")
CACHE = PROJECT_ROOT / "cache"
GEOMETRY_CACHE = CACHE / "geometry_data"
FONT = RESOURCES / "fonts" / "RobotoMono-Regular.ttf"
FONT_PATH = str(FONT.resolve().as_posix())
NC_FILE = DATA / "GEBCO_2025.nc"
TILES_DATA = DATA / "map_tiles"
HEIGHT_TILES_DB_PATH = TILES_DATA / "height_tiles.db"
TILES_CACHE = CACHE / "map_tiles"
SUN_LUT = DATA / "sun_lut.npy"

GEOMETRY_CACHE.mkdir(parents=True, exist_ok=True)
TILES_CACHE.mkdir(parents=True, exist_ok=True)


def clear_directory(dir_path):
    if not os.path.exists(dir_path):
        logger.warning("The directory %s does not exist.", dir_path)
        return

    for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error("Failed to delete %s", file_path, exc_info=True)
