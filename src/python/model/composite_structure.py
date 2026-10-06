from typing import Callable

from pyglm import glm

from rendering.drawables.model_batch import SurfaceEntityModelBatch
from rendering.scene.entity import Entity


class CompositeStructure:
    def __init__(self,
                 model: SurfaceEntityModelBatch,
                 parent=None,
                 translation=glm.dvec3(0.0, 0.0, 0.0),
                 rotation=glm.angleAxis(glm.radians(0.0), glm.dvec3(1, 0, 0)),
                 scale=glm.dvec3(1.0, 1.0, 1.0),
                 power_scaling=glm.dvec3(0.0, 0.0, 0.0),
                 animation: Callable[[Entity, float], None] = None,
                 animation_speed=1):
        """
        Args:
            model (EntityModelBatch): The Model data to be rendered for this component.
            parent (Optional[CompositeStructure]): The parent structure this model is
                attached to, used for hierarchical transformations. Defaults to None.
            translation (Optional[glm.dvec3]): The position offset relative to the parent
                or world origin. Defaults to None.
            rotation (Optional[glm.quat]): The orientation of the model. Defaults to None.
            scale (glm.dvec3): The base XYZ scaling factors.
                Defaults to glm.dvec3(1.0, 1.0, 1.0).
            power_scaling (glm.dvec3): Multiplier for power scaling. Defaults to glm.dvec3(0.0, 0.0, 0.0).
            animation (Optional[Callable[[Entity, float], None]]): A function or lambda
                executed every frame to update the entity's state. Defaults to None.
            animation_speed (float): A scalar multiplier applied to the delta time
                within the animation logic. Defaults to 1.
        """
        self.model = model
        self.parent = parent
        self.translation = translation
        self.rotation = rotation
        self.scale = scale
        self.power_scaling = power_scaling
        self.animation = animation
        self.animation_speed = animation_speed
