import logging

import numpy as np
from PIL import Image

from util.coordinate_constants import GLOBE_RADIUS
from util.paths import SUN_LUT, DATA

logger = logging.getLogger(__name__)

atmosphere_radius = 1.1 * GLOBE_RADIUS
atmosphere_thickness = atmosphere_radius - GLOBE_RADIUS
h_scale = 0.01 * GLOBE_RADIUS

WIDTH = 512
HEIGHT = 512
SAMPLES = 200


def generate_lut():
    logger.info("Generating Sun Optical Depth LUT")

    # Create normalized UV grids
    u = np.linspace(0, 1, WIDTH, dtype=np.float32)
    v = np.linspace(1, 0, HEIGHT, dtype=np.float32)
    u, v = np.meshgrid(u, v)

    # Reverse the texture coordinate mapping
    # float u = (cos_theta_sun + 1.0) * 0.5; -> cos_theta_sun = u * 2.0 - 1.0
    # float v = height / atmosphere_thickness; -> height = v * atmosphere_thickness
    cos_theta_sun = u * 2.0 - 1.0
    height = v * atmosphere_thickness

    # Calculate radial distance from planet center
    r = GLOBE_RADIUS + height

    # 3. Setup vector geometry
    # Place our sample positions on the Y axis
    pos = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    pos[:, :, 1] = r

    # Calculate sun direction based on cos_theta_sun
    sin_theta_sun = np.sqrt(np.maximum(0.0, 1.0 - cos_theta_sun ** 2))
    sun_dir = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    sun_dir[:, :, 0] = sin_theta_sun  # X component
    sun_dir[:, :, 1] = cos_theta_sun  # Y component (Up)

    # Ray-Atmosphere Intersection
    # Replicating: raySphereIntersect(pos, sun_dir, atmosphere_radius)
    b = np.sum(pos * sun_dir, axis=2)
    c = r ** 2 - atmosphere_radius ** 2
    h_val = b ** 2 - c

    # We only care about the positive intersection (tAtm.y) since we start inside the atmosphere
    t_end = -b + np.sqrt(np.maximum(0.0, h_val))

    # Ray Marching Loop
    segment_length = t_end / SAMPLES
    sun_optical_depth = np.zeros((HEIGHT, WIDTH), dtype=np.float32)

    for i in range(SAMPLES):
        # Sample at the middle of the segment
        t_current = (i + 0.5) * segment_length

        # Broadcast t_current to 3D for vector multiplication
        t_current_3d = t_current[:, :, np.newaxis]

        sample_pos = pos + sun_dir * t_current_3d
        sample_height = np.linalg.norm(sample_pos, axis=2) - GLOBE_RADIUS

        # Calculate local density and accumulate
        local_density = np.exp(-np.maximum(sample_height, 0.0) / h_scale) * segment_length
        sun_optical_depth += local_density

    np.save(SUN_LUT, sun_optical_depth)

    img = np.log1p(sun_optical_depth)
    img = (255 * img / img.max()).astype(np.uint8)
    Image.fromarray(img).save(DATA / "temp.png")

    logger.info("Sun Optical Depth LUT generation complete")
    logger.info("Shape: %s", sun_optical_depth.shape)
    logger.info("Data min: %.4f, max: %.4f", sun_optical_depth.min(), sun_optical_depth.max())


if __name__ == "__main__":
    generate_lut()
