import copy
import math
import random
import uuid
from collections import defaultdict

import numpy as np
from pyglm import glm

from model.composite_structure import CompositeStructure
from model.geo_pos import GeoPos
from model.power_plant import PowerPlant
from rendering.drawables.model_batch import SurfaceEntityModelBatch, SURFACE_ENTITY_FORMAT
from rendering.drawables.culled_model_batch import GpuInstanceCuller
from rendering.shaders.compute_shader import ComputeShader
from rendering.geometry.mesh_loader import mesh_from_file
from rendering.scene.entity import Entity
from rendering.scene.surface_entity import SurfaceEntity
from rendering.textures.texture import Texture
from util.config import config
from util.coordinate_constants import GLOBE_RADIUS
from util.coordinate_conversion import haversine_distance, geo_pos_to_terrain_elevation
from util.startup import checkpoint


def get_plants_bbox(plants: list[PowerPlant], min_lon, min_lat, max_lon, max_lat):
    """Returns PowerPlants within the specified bounding box"""
    return [
        p for p in plants
        if (
                min_lon <= p.longitude <= max_lon and
                min_lat <= p.latitude <= max_lat
        )
    ]

def get_proximity_merged_plants(plants: dict[GeoPos, PowerPlant], radius_m=10_000):
    """Combines nearby PowerPlants
        Params:
            radius_m: max distance between plants to merge them
        Returns:
            A new list of merged PowerPlants
    """
    cell_size = radius_m / GLOBE_RADIUS
    grid = defaultdict(list)
    merged: dict[GeoPos, PowerPlant] = dict()

    for location, plant in plants.items():
        cx = int(location.lon / cell_size)
        cy = int(location.lat / cell_size)

        found = None

        # search neighbors
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid[(cx + dx, cy + dy)]:
                    if haversine_distance(location, other.pos) <= radius_m:
                        found = other
                        break
                if found:
                    break
            if found:
                break

        if found:
            found.leistung_kw = (
                (found.leistung_kw or 0.0) + (plant.leistung_kw or 0.0)
            )

        else:
            plant_copy = copy.copy(plant)  # don't mutate elements in plants
            merged[location] = plant_copy
            grid[(cx, cy)].append(plant_copy)

    return merged


def build_composite_entities(plants: list[PowerPlant],
                             composite_structure_dict: dict[str, list[CompositeStructure]]):
    """
        Constructs and positions multi-part 3D entities based on power plant data.

        For each plant, this function creates a group of entities defined by the
        composite_structures. The first structure (root) is positioned on a spherical
        coordinate system based on the plant's geographic location and scaled
        proportionally to its power output. Subsequent structures are attached
        as child parts to their designated parents within the hierarchy.

        Args:
            plants (dict[GeoPos, PowerPlant]): The list of Power Plant data Points to create
                the composite entities for.
            composite_structure_dict (list[CompositeStructure]): A blueprint list
                defining the hierarchy, models, offsets, and animations for the
                individual parts of the composite model.
            heightmap (np.ndarray): The height map of the globe

        Note:
            The function assumes that `composite_structure.parent` is an integer index
            referencing a previously created entity in the `parts` list for that plant.
            Therefor parents must be positioned before their children in the
            composite_structures list.
        """
    for plant_index, plant in enumerate(plants):
        if plant_index % 100 == 0:
            checkpoint()
        parts: list[Entity] = []
        composite_structures = composite_structure_dict.get(plant.energietraeger or "")
        if not composite_structures:
            continue
        for composite_structure in composite_structures:
            geo_pos = plant.pos

            parent = parts[composite_structure.parent] if composite_structure.parent is not None else None
            entity = SurfaceEntity(geo_pos, parent=parent)

            power_ratio = 1

            entity.translation += composite_structure.translation
            entity.rotation = composite_structure.rotation
            entity.scale.x *= composite_structure.scale.x + composite_structure.power_scaling.x * power_ratio
            entity.scale.y *= composite_structure.scale.y + composite_structure.power_scaling.y * power_ratio
            entity.scale.z *= composite_structure.scale.z + composite_structure.power_scaling.z * power_ratio

            entity.animation = composite_structure.animation
            entity.animation_speed = composite_structure.animation_speed * power_ratio

            parts.append(entity)
            composite_structure.model.entities.append(entity)


def generate_random_plants(count):
    return {location:
                PowerPlant(plant_id=uuid.uuid4().int, pos=location)
            for location in [
                GeoPos.from_degrees(
                    lon=random.uniform(-10, 40),
                    lat=random.uniform(35, 71),
                )
                for _ in range(count)
            ]
            }


POWER_MODEL_CULL_DISTANCE_FACTOR = 1000.0


def create_surface_model_batch(mesh, cull_shader: ComputeShader):
    culler = GpuInstanceCuller(mesh, SURFACE_ENTITY_FORMAT, cull_shader)
    batch = SurfaceEntityModelBatch(mesh, culler=culler)
    batch.shader_uniforms["modelScale"] = float(10 ** config.graphics.power_plant_scale)
    batch.cull_uniforms.update({
        "modelScale": lambda: batch.shader_uniforms["modelScale"],
        "cullDistanceFactor": POWER_MODEL_CULL_DISTANCE_FACTOR,
        "meshRadius": float(mesh.base_radius or 0.0),
    })
    return batch


def create_wind_turbine_composite_structure(cull_shader: ComputeShader):
    rotate_y = lambda entity, delta_time: (
        setattr(entity, "rotation",
                glm.angleAxis((2 * glm.pi()) * delta_time * entity.animation_speed,
                              glm.dvec3(0, 1, 0)) * entity.rotation))

    wind_turbine_pole = create_surface_model_batch(mesh_from_file("windmill_base"), cull_shader)
    wind_turbine_rotors = create_surface_model_batch(mesh_from_file("windmill_blades"), cull_shader)
    structure = [CompositeStructure(model=wind_turbine_pole),
                 CompositeStructure(model=wind_turbine_rotors,
                                    parent=0,
                                    translation=glm.dvec3(0.0, -1.13475, 6.33321),
                                    animation=rotate_y)]
    return structure


def create_simple_composite_structure(model: str, cull_shader: ComputeShader, texture: str | None = None):
    mesh = mesh_from_file(model)
    if texture: mesh.textures["diffuse"] = Texture.from_file(texture, repeat_t=False)
    return [CompositeStructure(model=create_surface_model_batch(mesh, cull_shader))]


def create_picture_composite_structure(texture: str, cull_shader: ComputeShader):
    mesh = mesh_from_file("cube")
    mesh.textures["diffuse"] = Texture.from_file(texture, repeat_t=False)
    return [CompositeStructure(model=create_surface_model_batch(mesh, cull_shader))]
