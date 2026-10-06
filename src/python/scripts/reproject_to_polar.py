import numpy as np
from PIL import Image

from util.paths import TEXTURES
from util.polar_projection import equirectangular_to_polar


if __name__ == "__main__":
    Image.MAX_IMAGE_PIXELS = 233280000

    img_name = "normal.png"
    img = np.array(Image.open(TEXTURES / "globe" / img_name))

    north = equirectangular_to_polar(img, max_latitude=10, is_north=True, output_size=4096)
    south = equirectangular_to_polar(img, max_latitude=10, is_north=False, output_size=4096)

    Image.fromarray(north).save(TEXTURES / "globe" / "north_pole" / img_name.replace(".jpg", ".png"))
    Image.fromarray(south).save(TEXTURES / "globe" / "south_pole" / img_name.replace(".jpg", ".png"))
