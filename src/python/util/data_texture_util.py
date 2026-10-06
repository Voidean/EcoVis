import math
from typing import Tuple

import numpy as np
from pyglm import glm


def extract_channel(data: np.ndarray) -> np.ndarray:
    if data.ndim == 2:
        return data
    elif data.ndim == 3:
        return data[..., 0]
    else:
        raise ValueError()


def pack_wind_rg(vector_field: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    u, v = vector_field
    dtype = u.dtype
    u, v = extract_channel(u), extract_channel(v)

    packed = np.zeros((*u.shape, 2), dtype=dtype)
    packed[..., 0] = u
    packed[..., 1] = v

    if np.issubdtype(dtype, np.floating):
        packed = (packed + 1.0) / 2.0

    return packed


def decode_to_float(data: np.ndarray) -> np.ndarray:
    if not np.issubdtype(data.dtype, np.integer): return data

    mid_point = (np.iinfo(data.dtype).max + 1) / 2
    return (data.astype(np.float32) - mid_point) / (mid_point - 1)


def wind_speed_from_uv(vector_field: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    u, v = vector_field
    dtype = u.dtype

    u, v = decode_to_float(extract_channel(u)), decode_to_float(extract_channel(v))

    speed = np.sqrt(u ** 2 + v ** 2)

    max_speed = math.sqrt(2)
    if max_speed > 0:
        speed /= max_speed

    if np.issubdtype(dtype, np.integer):
        speed = np.clip(speed, 0, 1) * np.iinfo(dtype).max

    return speed.astype(dtype=dtype)


def bilinear_sample(data: np.ndarray, uv: glm.vec2) -> float:
    data = extract_channel(data)

    h, w = data.shape

    # Repeat X, clamp Y
    u = uv.x % 1.0
    v = max(0.0, min(uv.y, 1.0))

    # Scale UV to pixel coordinates
    tx = u * (w - 1)
    ty = (1.0 - v) * (h - 1)

    # Get the integer coordinates of the 4 surrounding pixels
    x0 = int(tx)
    y0 = int(ty)
    x1 = min(x0 + 1, w - 1)
    y1 = min(y0 + 1, h - 1)

    # Calculate weights
    fx = tx - x0
    fy = ty - y0

    # Sample the 4 pixels
    p00 = float(data[y0, x0])
    p10 = float(data[y0, x1])
    p01 = float(data[y1, x0])
    p11 = float(data[y1, x1])

    # Linear blend along X for both rows
    top = p00 + fx * (p10 - p00)
    bottom = p01 + fx * (p11 - p01)

    # Linear blend along Y
    result = top + fy * (bottom - top)

    if np.issubdtype(data.dtype, np.integer):
        result /= np.iinfo(data.dtype).max

    return result


def scale(value, start: float, end: float):
    return (value - start) / (end - start)


def unscale(value, start: float, end: float):
    return value * (end - start) + start


import numpy as np


def bilinear_sample_area(img: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """
    Performs fast vectorized bilinear interpolation over a 2D or 3D grid.

    Parameters:
        img: 2D (H, W) or 3D (H, W, C) source array
        ys: 1D array of fractional row coordinates
        xs: 1D array of fractional column coordinates
    """
    h_in = img.shape[0]
    w_in = img.shape[1]

    # Safely clamp coordinates to protect edges
    ys = np.clip(ys, 0, h_in - 1)
    xs = np.clip(xs, 0, w_in - 1)

    # Get lower and upper bounding integer indices
    y0 = np.floor(ys).astype(np.int32)
    y1 = np.minimum(y0 + 1, h_in - 1)
    x0 = np.floor(xs).astype(np.int32)
    x1 = np.minimum(x0 + 1, w_in - 1)

    # Compute fractional interpolation weights
    dy = (ys - y0)[:, np.newaxis]
    dx = (xs - x0)[np.newaxis, :]

    # Broadcast grids for 2D sampling
    y0_g, y1_g = y0[:, np.newaxis], y1[:, np.newaxis]
    x0_g, x1_g = x0[np.newaxis, :], x1[np.newaxis, :]

    # Sample the 4 neighboring quadrants
    ia = img[y0_g, x0_g]
    ib = img[y0_g, x1_g]
    ic = img[y1_g, x0_g]
    id = img[y1_g, x1_g]

    # Interpolate linear weights
    wa = (1.0 - dx) * (1.0 - dy)
    wb = dx * (1.0 - dy)
    wc = (1.0 - dx) * dy
    wd = dx * dy

    # If the input image has channels, append an axis to the weights
    # so they broadcast correctly against the (H, W, C) sampled arrays
    if img.ndim == 3:
        wa = wa[..., np.newaxis]
        wb = wb[..., np.newaxis]
        wc = wc[..., np.newaxis]
        wd = wd[..., np.newaxis]

    # Accumulate values and return casted to output format
    res = ia * wa + ib * wb + ic * wc + id * wd

    return np.round(res).astype(img.dtype)


def pad_channels(data: np.ndarray, expected_channels: int) -> np.ndarray:
    # Already correct
    if data.ndim == 3 and data.shape[-1] == expected_channels:
        return data

    # Grayscale (H, W)
    if data.ndim == 2:
        if expected_channels == 1:
            return data[..., None]

        if expected_channels == 4:
            rgb = np.repeat(data[..., None], 3, axis=-1)
            alpha = np.full((*data.shape, 1), 255, dtype=data.dtype)
            return np.concatenate((rgb, alpha), axis=-1)

    # Single-channel (H, W, 1)
    if data.ndim == 3 and data.shape[-1] == 1:
        if expected_channels == 1:
            return data

        if expected_channels == 4:
            rgb = np.repeat(data, 3, axis=-1)
            alpha = np.full((*data.shape[:2], 1), 255, dtype=data.dtype)
            return np.concatenate((rgb, alpha), axis=-1)

    # RGB to RGBA
    if data.ndim == 3 and data.shape[-1] == 3 and expected_channels == 4:
        alpha = np.full((*data.shape[:2], 1), 255, dtype=data.dtype)
        return np.concatenate((data, alpha), axis=-1)

    raise ValueError(
        f"Cannot convert image with shape {data.shape} "
        f"to {expected_channels} channels."
    )
