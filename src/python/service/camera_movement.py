import math
from typing import Any

from pyglm import glm

from input import Input
from model.projection import Projection
from rendering.scene.camera import Camera
from util.config import config
from util.coordinate_constants import GLOBE_RADIUS, WORLD_UP
from util.coordinate_conversion import world_pos_altitude
from util.input_constants import MouseButton
from util.screen_projection import screen_space_to_world_space_approx, screen_space_to_world_space

MIN_ORBIT_ANGLE = math.radians(1.5)
MAX_ORBIT_ANGLE = math.radians(85.0)


class CameraMovement:
    def __init__(self, input: Input) -> None:
        self.input = input
        self.moved = False
        self.drag_pivot = None  # Persistent anchor locked at the start of a drag session
        self.altitude = 0.0

    def update_movement(self, camera: Camera, delta_time: float, projection: Projection):
        if self.input.drag_button is None:
            self.drag_pivot = None

        self.altitude = world_pos_altitude(camera.translation)

        self.handle_fov(camera, delta_time)

        self.handle_zoom(camera, projection)
        self.handle_pan_drag(camera, projection)
        self.handle_orbit_drag(camera, projection)

        self.handle_translate(camera, projection, delta_time)
        self.handle_key_rotate(camera, projection, delta_time)
        self.handle_rotate(camera, projection)

        if self.moved:
            camera.apply_view_transform()
            self.moved = False

        self.input.drag_delta = 0, 0
        self.input.scroll_delta = 0

    def handle_zoom(self, camera: Camera, projection: Projection):
        if not self.input.scroll_delta: return

        point = screen_space_to_world_space_approx(self.input.mouse_pos, camera, projection)

        # Fallback point if nothing was hit
        if point is None:
            _, ray_dir = camera.screen_ray(self.input.mouse_pos)
            fallback_dist = max(self.altitude * 2.0, GLOBE_RADIUS * 0.0001)

            point = camera.translation + ray_dir * fallback_dist

        # Zoom towards point
        to_point = point - camera.translation
        distance = glm.length(to_point)

        if distance < 1e-6: return

        direction = to_point / distance
        speed = config.input.scroll_speed * max(distance * 0.15, GLOBE_RADIUS * 0.0001)
        movement = self.input.scroll_delta * speed

        # Prevent passing the target point
        if movement > 0: movement = min(movement, distance)

        new_position = camera.translation + direction * movement

        # Prevent going below ground
        if projection == Projection.GLOBE:
            radius = glm.length(new_position)
            if radius < GLOBE_RADIUS:
                new_position = (glm.normalize(new_position) * GLOBE_RADIUS)
        else:
            new_position.z = max(0.0, new_position.z)

        camera.translation = new_position

        self.input.scroll_delta = 0
        self.moved = True

    def handle_pan_drag(self, camera: Camera, projection: Projection):
        if self.input.drag_button != MouseButton.LEFT: return

        mouse_dx, mouse_dy = self.input.drag_delta
        if mouse_dx == 0 and mouse_dy == 0: return

        # Compute world-space pixel size at this altitude based on FOV
        pixel_world_size = 2.0 * max(0.1, self.altitude) * math.tan(camera.fov * 0.5) / camera.height

        # Extract current screen right and up vectors in world-space from the Inverse View Matrix
        inv_view = glm.inverse(camera.view_transform)
        cam_right = glm.normalize(glm.dvec3(inv_view * glm.dvec4(1.0, 0.0, 0.0, 0.0)))
        cam_up = glm.normalize(glm.dvec3(inv_view * glm.dvec4(0.0, 1.0, 0.0, 0.0)))

        if projection == Projection.GLOBE:
            # For a globe, convert linear translation stride into an angular orbit
            cam_dist = glm.length(camera.translation)
            angle_x = ((mouse_dx * pixel_world_size) / cam_dist) * 2.0
            angle_y = ((-mouse_dy * pixel_world_size) / cam_dist) * 2.0

            # Rotate around camera's local axes to maintain constant altitude and look normal
            rot_x = glm.angleAxis(-angle_x, cam_up)
            rot_y = glm.angleAxis(angle_y, cam_right)
            combined_rot = rot_x * rot_y

            camera.translation = combined_rot * camera.translation
            camera.rotation = combined_rot * camera.rotation
        else:
            # Project view axes onto the flat XY plane
            cam_right_flat = glm.dvec3(cam_right.x, cam_right.y, 0.0)
            cam_up_flat = glm.dvec3(cam_up.x, cam_up.y, 0.0)

            if glm.length2(cam_right_flat) > 0.001: cam_right_flat = glm.normalize(cam_right_flat)
            if glm.length2(cam_up_flat) > 0.001: cam_up_flat = glm.normalize(cam_up_flat)

            # Move camera inversely to drag direction to pull the map under the cursor
            camera.translation -= cam_right_flat * (mouse_dx * pixel_world_size)
            camera.translation += cam_up_flat * (mouse_dy * pixel_world_size)

        self.moved = True

    def handle_orbit_drag(self, camera: Camera, projection: Projection):
        if self.input.drag_button != MouseButton.RIGHT: return

        mouse_dx, mouse_dy = self.input.drag_delta
        if mouse_dx == 0 and mouse_dy == 0: return

        if self.drag_pivot is None:
            self.drag_pivot = screen_space_to_world_space(self.input.drag_start_pos, camera, self.input.frame_buffer)
        if self.drag_pivot is None:
            return

        yaw_delta = -mouse_dx * config.input.mouse_sensitivity
        pitch_delta = mouse_dy * config.input.mouse_sensitivity

        c, q = camera.translation, camera.rotation

        c, q = self.orbit_yaw(yaw_delta, c, q, projection)
        c, q = self.orbit_pitch(pitch_delta, c, q, projection)
        c, q = self.orbit_correct_roll(c, q, projection)

        camera.translation, camera.rotation = c, q

        self.moved = True

    def orbit_yaw(self, yaw_delta, c, q, projection: Projection) -> tuple[Any, Any]:
        yaw_quat = glm.angleAxis(yaw_delta, projection.up(self.drag_pivot))

        c = self.drag_pivot + yaw_quat * (c - self.drag_pivot)
        q = yaw_quat * q
        return c, q

    def orbit_pitch(self, pitch_delta, c, q, projection: Projection):
        # Update target_up for the intermediate yawed position
        target_up_yawed = glm.normalize(c) if projection == Projection.GLOBE else WORLD_UP
        f_yawed = q * glm.dvec3(0.0, -1.0, 0.0)

        # Current pitch is the angle between the forward vector and the horizon plane.
        vertical = glm.dot(f_yawed, -target_up_yawed)
        horizontal = glm.length(glm.cross(f_yawed, target_up_yawed))

        current_pitch = math.atan2(vertical, horizontal)

        desired_pitch = glm.clamp(current_pitch + pitch_delta, MIN_ORBIT_ANGLE, MAX_ORBIT_ANGLE)
        actual_pitch_delta = desired_pitch - current_pitch

        # Pitch axis must be strictly horizontal relative to local ground to avoid skew
        right_yawed = glm.cross(target_up_yawed, f_yawed)
        if glm.length(right_yawed) > 1e-6:
            pitch_axis = glm.normalize(right_yawed)
        else:
            pitch_axis = q * glm.dvec3(1.0, 0.0, 0.0)

        # Apply Pitch rigidly around the pivot
        pitch_quat = glm.angleAxis(actual_pitch_delta, pitch_axis)
        c_new = self.drag_pivot + pitch_quat * (c - self.drag_pivot)
        q_new = pitch_quat * q
        return c_new, q_new

    def orbit_correct_roll(self, c, q, projection: Projection):
        target_up_final = glm.normalize(c) if projection == Projection.GLOBE else WORLD_UP

        # To keep p perfectly under the cursor, we may ONLY twist the camera around the ray to p.
        ray_dir = self.drag_pivot - c
        ray_len = glm.length(ray_dir)

        if ray_len > 1e-6:
            ray_dir = ray_dir / ray_len
            r_temp = q * glm.dvec3(1.0, 0.0, 0.0)

            # Solve for twist angle `theta` so that r_temp becomes strictly orthogonal to target_up_final.
            # This resolves to the trigonometric equation: a*cos(theta) + b*sin(theta) = C
            a = glm.dot(r_temp, target_up_final)
            b = glm.dot(glm.cross(ray_dir, r_temp), target_up_final)
            c_trig = glm.dot(ray_dir, r_temp) * glm.dot(ray_dir, target_up_final)

            a_ = a - c_trig
            b_ = b
            c_val = -c_trig

            r_val = math.sqrt(a_ * a_ + b_ * b_)

            alignment = abs(glm.dot(ray_dir, target_up_final))

            if r_val > 1e-6 and alignment <= 0.99:
                ratio = glm.clamp(c_val / r_val, -1.0, 1.0)
                alpha = math.atan2(b_, a_)

                # Two valid solutions exist (upright and upside-down)
                theta1 = alpha + math.acos(ratio)
                theta2 = alpha - math.acos(ratio)

                q1 = glm.normalize(glm.angleAxis(theta1, ray_dir) * q)
                q2 = glm.normalize(glm.angleAxis(theta2, ray_dir) * q)

                cam_up1 = q1 * glm.dvec3(0.0, 0.0, 1.0)
                cam_up2 = q2 * glm.dvec3(0.0, 0.0, 1.0)

                # Choose the solution that aligns positively with target up
                q_final = q1 if glm.dot(cam_up1, target_up_final) > glm.dot(cam_up2, target_up_final) else q2
            else:
                q_final = q
        else:
            q_final = q
        return c, glm.normalize(q_final)

    def handle_fov(self, camera: Camera, delta_time: float):
        if not self.input.keys_down: return

        fov_delta = 0.0

        if config.keybinds.decrease_fov in self.input.keys_down:
            fov_delta -= 1.0
        if config.keybinds.increase_fov in self.input.keys_down:
            fov_delta += 1.0

        if fov_delta:
            fov = camera.fov + math.radians((fov_delta * 10 * config.input.key_step_size * delta_time))
            fov = max(0.0, min(math.radians(100.0), fov))
            camera.set_fov(fov)

    def handle_translate(self, camera: Camera, projection: Projection, delta_time: float):
        if not self.input.keys_down: return
        direction = glm.dvec3(0.0, 0.0, 0.0)

        kb = config.keybinds
        if kb.move_forward in self.input.keys_down: direction.y += 1.0
        if kb.move_back in self.input.keys_down: direction.y -= 1.0

        if kb.move_left in self.input.keys_down: direction.x += 1.0
        if kb.move_right in self.input.keys_down: direction.x -= 1.0

        if kb.move_up in self.input.keys_down: direction.z += 1.0
        if kb.move_down in self.input.keys_down: direction.z -= 1.0

        if glm.length2(direction) == 0: return
        direction = glm.normalize(direction)

        up = projection.up(camera.translation)

        cam_forward = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
        flat_forward = cam_forward - up * glm.dot(cam_forward, up)

        if glm.length2(flat_forward) > 1e-6:
            flat_forward = glm.normalize(flat_forward)
        else:
            # Fallback if looking directly up or down
            cam_right = camera.rotation * glm.dvec3(1.0, 0.0, 0.0)
            flat_forward = glm.normalize(glm.cross(cam_right, up))

        flat_right = glm.normalize(glm.cross(up, flat_forward))

        speed = max(self.altitude, GLOBE_RADIUS * 0.0001) * config.input.key_step_size * delta_time

        if projection == Projection.GLOBE:
            lateral_dir = (flat_forward * direction.y) + (flat_right * direction.x)
            lateral_mag = glm.length(lateral_dir)

            if lateral_mag > 0:
                move_dir = lateral_dir / lateral_mag

                rot_axis = glm.cross(up, move_dir)

                theta = (lateral_mag * speed) / glm.length(camera.translation)

                orbit_rot = glm.angleAxis(theta, rot_axis)
                camera.translation = orbit_rot * camera.translation
                camera.rotation = orbit_rot * camera.rotation

                up = glm.normalize(camera.translation)

            if direction.z != 0 and not (direction.z <= 0 and self.altitude <= 0):
                camera.translation += up * (direction.z * speed)
        else:
            move_vec = (flat_forward * direction.y) + (flat_right * direction.x) + (up * direction.z)
            camera.translation += move_vec * speed

        self.moved = True

    def handle_rotate(self, camera: Camera, projection: Projection):
        if self.input.drag_button != MouseButton.MIDDLE: return

        mouse_dx, mouse_dy = self.input.drag_delta
        if mouse_dx == 0 and mouse_dy == 0: return

        # Negative yaw delta ensures moving the mouse left rotates the camera left
        yaw_delta = -mouse_dx * config.input.mouse_sensitivity
        pitch_delta = mouse_dy * config.input.mouse_sensitivity

        up = projection.up(camera.translation)

        # Apply Yaw
        yaw_quat = glm.angleAxis(yaw_delta, up)
        camera.rotation = yaw_quat * camera.rotation

        # Calculate and Clamp Pitch
        # Current pitch is angle between forward vector and the horizon plane
        f_yawed = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
        sin_pitch = glm.clamp(glm.dot(f_yawed, -up), -1.0, 1.0)
        current_pitch = math.asin(sin_pitch)

        desired_pitch = glm.clamp(current_pitch + pitch_delta, -MAX_ORBIT_ANGLE, MAX_ORBIT_ANGLE)
        actual_pitch_delta = desired_pitch - current_pitch

        # Ensure pitch axis is strictly horizontal relative to local surface
        right_horizontal = glm.cross(up, f_yawed)
        if glm.length2(right_horizontal) > 1e-6:
            pitch_axis = glm.normalize(right_horizontal)
        else:
            pitch_axis = camera.rotation * glm.dvec3(1.0, 0.0, 0.0)

        # Apply Pitch rigidly
        pitch_quat = glm.angleAxis(actual_pitch_delta, pitch_axis)
        camera.rotation = pitch_quat * camera.rotation

        self.correct_roll(camera, projection)

        self.moved = True

    def handle_key_rotate(self, camera: Camera, projection: Projection, delta_time: float):
        """Rotate in place while the configured rotation keys are held."""
        if not self.input.keys_down:
            return

        kb = config.keybinds
        yaw_direction = 0.0
        pitch_direction = 0.0

        if kb.rotate_left in self.input.keys_down:
            yaw_direction += 1.0
        if kb.rotate_right in self.input.keys_down:
            yaw_direction -= 1.0
        if kb.rotate_up in self.input.keys_down:
            pitch_direction -= 1.0
        if kb.rotate_down in self.input.keys_down:
            pitch_direction += 1.0

        if yaw_direction == 0.0 and pitch_direction == 0.0:
            return

        # Match the FOV keyboard control's speed scaling while keeping the
        # translation unchanged: these controls only change orientation.
        rotation_speed = math.radians(60.0) * config.input.key_step_size
        yaw_delta = yaw_direction * rotation_speed * delta_time
        pitch_delta = pitch_direction * rotation_speed * delta_time

        up = projection.up(camera.translation)

        if yaw_delta:
            camera.rotation = glm.angleAxis(yaw_delta, up) * camera.rotation

        # Keep pitch within the same limits used by middle-mouse rotation.
        f_yawed = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
        current_pitch = math.asin(glm.clamp(glm.dot(f_yawed, -up), -1.0, 1.0))
        desired_pitch = glm.clamp(current_pitch + pitch_delta, -MAX_ORBIT_ANGLE, MAX_ORBIT_ANGLE)
        actual_pitch_delta = desired_pitch - current_pitch

        if actual_pitch_delta:
            right_horizontal = glm.cross(up, f_yawed)
            if glm.length2(right_horizontal) > 1e-6:
                pitch_axis = glm.normalize(right_horizontal)
            else:
                pitch_axis = camera.rotation * glm.dvec3(1.0, 0.0, 0.0)
            camera.rotation = glm.angleAxis(actual_pitch_delta, pitch_axis) * camera.rotation

        self.correct_roll(camera, projection)
        self.moved = True

    def correct_roll(self, camera, projection):
        # Correct Roll
        # Re-orthogonalize the camera to lock its local 'Up' vector to the world 'Up' vector
        up = projection.up(camera.translation)

        f_final = camera.rotation * glm.dvec3(0.0, -1.0, 0.0)
        r_final = glm.normalize(glm.cross(up, f_final))
        u_final = glm.cross(f_final, r_final)

        # Reconstruct quaternion from orthogonal basis axes: X=Right, Y=Back(-Forward), Z=Up
        rot_mat = glm.dmat3(r_final, -f_final, u_final)
        camera.rotation = glm.normalize(glm.quat_cast(rot_mat))
