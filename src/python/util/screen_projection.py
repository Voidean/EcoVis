import math
import platform

from pyglm import glm

from model.projection import Projection
from rendering.scene.camera import Camera
from rendering.textures.frame_buffer import FrameBuffer
from util.coordinate_constants import GLOBE_RADIUS


def world_space_to_screen_space(world_pos: glm.dvec3, camera: Camera) -> glm.dvec2 | None:
    viewport = glm.dvec4(0, 0, camera.width, camera.height)
    x, y, depth = glm.projectZO(world_pos, camera.view_transform, camera.projection_transform, viewport)

    if depth < 0.0 or depth > 1.0: return None

    y = camera.height - y  # OpenGL screen coordinates start at bottom-left
    if platform.system() != "Windows": x, y = x / camera.pixel_scale_x, y / camera.pixel_scale_y
    return glm.dvec2(x, y)


def screen_space_to_world_space(screen_pos, camera: Camera, frame_buffer: FrameBuffer) -> glm.dvec3 | None:
    # Creates sync point with GPU, don't call every frame, use screen_space_to_world_space_approx instead!
    x, y = screen_pos
    if platform.system() != "Windows": x, y = x * camera.pixel_scale_x, y * camera.pixel_scale_y
    y = camera.height - y  # OpenGL screen coordinates start at bottom-left
    depth = frame_buffer.read_depth_pixel(x, y)

    if depth <= 0.0: return None

    screen_pos = glm.dvec3(x, y, depth)
    viewport = glm.dvec4(0, 0, camera.width, camera.height)
    return glm.unProjectZO(screen_pos, camera.view_transform, camera.projection_transform, viewport)


def intersect_globe(ray_origin, ray_dir):
    if glm.length(ray_origin) < GLOBE_RADIUS: return None # TODO IMPROVE

    a = glm.dot(ray_dir, ray_dir)
    b = 2.0 * glm.dot(ray_origin, ray_dir)
    c = glm.dot(ray_origin, ray_origin) - GLOBE_RADIUS ** 2

    discriminant = b * b - 4 * a * c

    if discriminant < 0:
        return None

    sqrt_d = math.sqrt(discriminant)

    t1 = (-b - sqrt_d) / (2 * a)
    t2 = (-b + sqrt_d) / (2 * a)

    valid_ts = [v for v in (t1, t2) if v > 0]

    if not valid_ts: return None

    t = min(valid_ts)
    return ray_origin + ray_dir * t


def intersect_plane(ray_origin, ray_dir):
    if abs(ray_dir.z) < 1e-6:
        return None

    t = -ray_origin.z / ray_dir.z

    if t < 0: return None

    return ray_origin + ray_dir * t


def intersect_surface(ray_origin, ray_dir, projection) -> glm.dvec3 | None:
    if projection == Projection.GLOBE:
        return intersect_globe(ray_origin, ray_dir)
    else:
        return intersect_plane(ray_origin, ray_dir)


def screen_space_to_world_space_approx(screen_pos, camera: Camera, projection: Projection) -> glm.dvec3 | None:
    if screen_pos is None: return None
    ray_origin, ray_dir = camera.screen_ray(screen_pos)
    return intersect_surface(ray_origin, ray_dir, projection)
