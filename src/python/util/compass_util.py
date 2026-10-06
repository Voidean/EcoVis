import math

from pyglm import glm

from model.projection import Projection
from rendering.scene.camera import Camera
from util.coordinate_constants import WORLD_UP


def get_camera_surface_foreshortening(camera: Camera, projection: Projection) -> float:
    """Return the orthographic vertical scale of the surface below the camera.

    A surface viewed straight on has a scale of one, while a surface viewed
    along its horizon collapses to a line.
    """
    cam_forward = glm.normalize(camera.rotation * glm.dvec3(0.0, -1.0, 0.0))
    return -glm.dot(cam_forward, projection.up(camera.translation))


def get_camera_heading(camera: Camera, projection: Projection) -> float:
    cam_forward = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
    cam_up = camera.rotation * glm.dvec3(0.0, 0.0, 1.0)
    cam_right = camera.rotation * glm.dvec3(1.0, 0.0, 0.0)

    if projection == Projection.GLOBE:
        up = glm.normalize(camera.translation)
        north_pole = glm.dvec3(0.0, 0.0, 1.0)
    else:
        up = WORLD_UP
        north_pole = glm.dvec3(0.0, 1.0, 0.0)

    tangent_north = north_pole - up * glm.dot(north_pole, up)
    if glm.length2(tangent_north) > 1e-6:
        tangent_north = glm.normalize(tangent_north)
    else:
        tangent_north = camera.rotation * glm.dvec3(0.0, 1.0, 0.0)

    tangent_east = glm.cross(up, tangent_north)

    fwd = cam_forward - up * glm.dot(cam_forward, up)
    if glm.length2(fwd) < 1e-6:
        # Fallback if looking directly up or down
        fwd = cam_up - up * glm.dot(cam_up, up)
    fwd = glm.normalize(fwd)

    yaw = math.atan2(glm.dot(fwd, tangent_east), glm.dot(fwd, tangent_north))

    right_horizontal = glm.cross(cam_forward, up)
    if glm.length2(right_horizontal) < 1e-6:
        # Fallback if looking directly up or down
        right_horizontal = glm.cross(cam_up, up)
    right_horizontal = glm.normalize(right_horizontal)

    up_horizontal = glm.cross(right_horizontal, cam_forward)

    roll = math.atan2(glm.dot(cam_right, up_horizontal), glm.dot(cam_right, right_horizontal))

    return yaw + roll + math.pi


def snap_camera_to_north(camera: Camera, projection: Projection):
    if projection == Projection.GLOBE:
        up = glm.normalize(camera.translation)
        north_pole = glm.dvec3(0.0, 0.0, 1.0)
    else:
        from util.coordinate_constants import WORLD_UP
        up = WORLD_UP
        north_pole = glm.dvec3(0.0, 1.0, 0.0)

    # Correct roll
    f_final = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
    r_final = glm.normalize(glm.cross(up, f_final))
    u_final = glm.cross(f_final, r_final)

    # Reconstruct quaternion from orthogonal basis axes: X=Right, Y=Back(-Forward), Z=Up
    rot_mat = glm.dmat3(r_final, -f_final, u_final)
    camera.rotation = glm.normalize(glm.quat_cast(rot_mat))

    # Establish tangent North
    tangent_north = north_pole - up * glm.dot(north_pole, up)
    if glm.length2(tangent_north) > 1e-6:
        tangent_north = glm.normalize(tangent_north)
    else:
        return  # Already exactly at the pole; yaw is undefined/irrelevant

    tangent_east = glm.cross(up, tangent_north)

    # Get forward vector projected onto the horizon
    cam_forward = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
    cam_up = camera.rotation * glm.dvec3(0.0, 0.0, 1.0)

    fwd = cam_forward - up * glm.dot(cam_forward, up)
    if glm.length2(fwd) < 1e-6:
        fwd = cam_up - up * glm.dot(cam_up, up)
    fwd = glm.normalize(fwd)

    # Calculate current yaw offset
    yaw = math.atan2(glm.dot(fwd, tangent_east), glm.dot(fwd, tangent_north))

    # Apply counter-rotation strictly around the local Up axis
    yaw_quat = glm.angleAxis(-yaw, up)
    camera.rotation = yaw_quat * camera.rotation
    camera.apply_view_transform()  # Force view matrix update
