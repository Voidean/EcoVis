from typing import Callable

from pyglm import glm

from rendering.data.gl_data_format import Instance
from util.coordinate_constants import WORLD_UP


class Entity:
    def __init__(
            self,
            translation=None, rotation=None, scale=None,
            animation: Callable[["Entity", float], None] = None,
            parent=None
    ):
        self.translation: glm.dvec3 = translation if translation else glm.dvec3(0.0, 0.0, 0.0)
        self.rotation: glm.dquat = rotation if rotation else glm.dquat(1.0, 0.0, 0.0, 0.0)
        self.scale: glm.dvec3 = scale if scale else glm.dvec3(1.0, 1.0, 1.0)

        self.animation = animation
        self.animation_speed = 1.0

        self.parent = parent

    def get_transform(self):
        model_transform = glm.translate(glm.dmat4(1.0), self.translation)  # 3. translate
        model_transform = model_transform * glm.mat4_cast(self.rotation)  # 2. rotate
        model_transform = glm.scale(model_transform, self.scale)  # 1. scale

        if self.parent:
            return self.parent.get_transform() * model_transform
        else:
            return model_transform

    def to_instance(self):
        return Instance(model=glm.mat4(self.get_transform()))

    def turn_to_vector(self, direction: glm.dvec3, world_up=WORLD_UP,
                       entity_forward=glm.dvec3(0.0, -1.0, 0.0), entity_up=WORLD_UP):
        """
        Aligns the Entity's 'entity_forward' axis to face 'direction',
        while keeping 'entity_up' aligned with 'world_up' as closely as possible.
        """
        tgt_forward = glm.normalize(direction)
        tgt_right = glm.normalize(glm.cross(world_up, tgt_forward))

        # Handle Gimbal Lock: If looking straight up or down, the cross product is zero.
        if glm.length2(tgt_right) < 0.001:
            fallback_axis = glm.dvec3(0, 1, 0) if abs(world_up.y) < 0.9 else glm.dvec3(1, 0, 0)
            tgt_right = glm.normalize(glm.cross(fallback_axis, tgt_forward))

        tgt_up = glm.cross(tgt_forward, tgt_right)

        # Create Matrix from Columns [Right, Up, Forward]
        target_basis = glm.dmat3(tgt_right, tgt_forward, tgt_up)

        # This defines where the axes are relative to the model.
        src_forward = glm.normalize(entity_forward)
        src_right = glm.normalize(glm.cross(entity_up, src_forward))
        src_up = glm.normalize(glm.cross(src_forward, src_right))

        source_basis = glm.dmat3(src_right, src_forward, src_up)

        # Calculate & Apply Rotation
        rotation_matrix = target_basis * glm.transpose(source_basis)

        self.rotation = glm.quat_cast(rotation_matrix)

    def rotate_local(self, angle, axis):
        local_rot = glm.angleAxis(angle, glm.normalize(axis))
        self.rotation = self.rotation * local_rot

    def animate(self, delta_time: float):
        if self.animation: self.animation(self, delta_time)

    def __repr__(self):
        return f"Entity(translation={self.translation}, rotation={self.rotation}, scale={self.scale})"
