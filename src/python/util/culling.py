import numpy as np


def cull_frustum(frustum_planes, point, radius) -> bool:
    for plane in frustum_planes:
        distance = np.dot(plane[:3], point.to_list()) + plane[3]
        if distance < -radius: return True
    return False
