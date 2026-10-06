import numpy as np


def equirectangular_to_polar(
    data: np.ndarray,
    max_latitude: float = 90.0,
    is_north: bool = True,
    output_size: int | None = None,
):
    """
    Reproject equirectangular data to a polar projection.

    Parameters
    ----------
    data : ndarray
        Shape (height,width) or (height,width,channels).
        Latitude runs from +90° (top) to -90° (bottom).
        Longitude runs from -180° to +180°.

    max_latitude : float
        Maximum latitude from the pole to include.
        90 -> whole hemisphere
        60 -> down to 30° latitude
        30 -> down to 60° latitude

    is_north : north vs south

    output_size : int
        Width and height of output.
        Default: radius*2 where radius=min(height,width)//2

    Returns
    -------
    ndarray
    """

    if data.ndim == 2:
        data = data[..., None]
        squeeze = True
    else:
        squeeze = False

    height, width, channels = data.shape

    if output_size is None:
        output_size = min(height, width)

    out = np.zeros((output_size, output_size, channels), dtype=data.dtype)

    center = (output_size - 1) / 2
    max_radius = center

    yy, xx = np.indices((output_size, output_size))

    dx = xx - center
    dy = yy - center

    radius = np.sqrt(dx**2 + dy**2)

    valid = radius <= max_radius

    # longitude
    lon = np.arctan2(dx, -dy)

    lon_deg = np.degrees(lon)

    # distance from pole
    angular_distance = radius / max_radius * max_latitude

    if is_north:
        lat_deg = 90.0 - angular_distance
    else:
        lat_deg = -90.0 + angular_distance

    # Convert to coordinates
    x = (lon_deg + 180.0) / 360.0 * (width - 1)
    y = (90.0 - lat_deg) / 180.0 * (height - 1)

    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)

    x1 = (x0 + 1) % width
    y1 = np.clip(y0 + 1, 0, height - 1)

    wx = x - x0
    wy = y - y0

    x0 %= width
    y0 = np.clip(y0, 0, height - 1)

    for c in range(channels):
        ia = data[y0, x0, c]
        ib = data[y0, x1, c]
        ic = data[y1, x0, c]
        id = data[y1, x1, c]

        out[..., c] = (
            ia * (1 - wx) * (1 - wy)
            + ib * wx * (1 - wy)
            + ic * (1 - wx) * wy
            + id * wx * wy
        )

    out[~valid] = 0

    if squeeze:
        out = out[..., 0]

    return out