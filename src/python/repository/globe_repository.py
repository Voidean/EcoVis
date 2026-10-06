import math

import numpy as np
from PIL import Image
from pyglm import glm

from rendering.data.gl_data_format import VertexFormat, GlDataAttribute, Vertex
from rendering.geometry.geometry_data import GeometryData
from rendering.textures.texture import load_image_data
from util.coordinate_constants import WORLD_UP, GLOBE_RADIUS
from util.coordinate_conversion import cube_to_sphere, sphere_to_uv, uv_to_terrain_elevation
from util.paths import TEXTURES


def calculate_rotation():
    # Calculate the rotation to put corners on poles
    # The vector (1,1,1) has to point towards (0,1,0)
    target_pole = WORLD_UP
    cube_corner = glm.normalize(glm.dvec3(1, 1, 1))
    rotation_axis = glm.cross(cube_corner, target_pole)
    angle = math.acos(glm.dot(cube_corner, target_pole))
    return glm.rotate(glm.dmat4(1.0), angle, rotation_axis)


rotation = calculate_rotation()

directions = [
    glm.dvec3(0, 0, 1),
    glm.dvec3(0, 0, -1),
    glm.dvec3(0, 1, 0),
    glm.dvec3(0, -1, 0),
    glm.dvec3(1, 0, 0),
    glm.dvec3(-1, 0, 0),
]


def create_face(normal: glm.dvec3, resolution, inverted=False) -> GeometryData:
    axis_a = glm.dvec3(normal.y, normal.z, normal.x)
    axis_b = glm.cross(normal, axis_a)
    vertices = []
    indices = []

    for y in range(resolution):
        for x in range(resolution):
            t = glm.vec2(x, y) / (resolution - 1.0)
            point = normal + axis_a * (2 * t.x - 1) + axis_b * (2 * t.y - 1)
            vertices.append(Vertex(position=point))

            if x != resolution - 1 and y != resolution - 1:
                vertex_index = x + y * resolution

                i1, i2, i3 = vertex_index, vertex_index + resolution + 1, vertex_index + resolution
                i4, i5, i6 = vertex_index, vertex_index + 1, vertex_index + resolution + 1

                if not inverted:
                    indices.extend([i1, i2, i3])
                    indices.extend([i4, i5, i6])
                else:  # If inverted, swap indices to flip the triangle facing direction
                    indices.extend([i1, i3, i2])
                    indices.extend([i4, i6, i5])

    return GeometryData(vertices, indices)


def create_sphere(resolution, inverted=False) -> GeometryData:
    faces_data = []
    for direction in directions:
        faces_data.append(create_face(direction, resolution, inverted))

    for i, face in enumerate(faces_data):
        # The direction vector is the center of the face in cube-space
        face_dir = directions[i]

        face_center_pos = cube_to_sphere(face_dir)
        face_center_pos = glm.dvec3(rotation * glm.dvec4(face_center_pos, 1.0))

        ref_uv = sphere_to_uv(face_center_pos)

        for vertex in face.vertices:
            vertex.position = glm.dvec3(cube_to_sphere(vertex.position))
            vertex.position = glm.dvec3(rotation * glm.dvec4(vertex.position, 1.0))  # Rotate so corners are on poles

            normal = glm.normalize(vertex.position)

            up = WORLD_UP
            if abs(glm.dot(normal, up)) > 0.99: up = glm.dvec3(1, 0, 0)

            tangent = glm.normalize(glm.cross(up, normal))
            bitangent = glm.normalize(glm.cross(normal, tangent))

            uv = sphere_to_uv(vertex.position)

            # Seam Correction: Use the face's rotated center as the anchor
            if uv.x - ref_uv.x > 0.5:
                uv.x -= 1.0
            elif uv.x - ref_uv.x < -0.5:
                uv.x += 1.0

            if not inverted:
                vertex.tangent = glm.vec3(tangent)
                vertex.bitangent = glm.vec3(bitangent)
                vertex.normal = glm.vec3(normal)
                vertex.uv = glm.vec2(uv)
            else:
                vertex.tangent = -glm.vec3(tangent)
                vertex.bitangent = -glm.vec3(bitangent)
                vertex.normal = -glm.vec3(normal)
                vertex.uv = glm.vec2(1.0 - uv.x, uv.y)

    # Finally, merge the faces
    all_vertices = []
    all_indices = []
    vertex_offset = 0

    for face in faces_data:
        all_vertices.extend(face.vertices)
        all_indices.extend([idx + vertex_offset for idx in face.indices])
        vertex_offset += len(face.vertices)

    return GeometryData(all_vertices, all_indices)


def create_globe(resolution, heightmap: np.ndarray, vertical_scale=10.0) -> GeometryData:
    geometry = create_sphere(resolution)

    for vertex in geometry.vertices:
        elevation = uv_to_terrain_elevation(vertex.uv, heightmap)
        vertex.position *= GLOBE_RADIUS + elevation * vertical_scale

    return geometry


def create_globe_from_path(resolution, heightmap_path: str, vertical_scale=10.0) -> GeometryData:
    heightmap_image = Image.open(TEXTURES / heightmap_path).convert("L")
    heightmap = load_image_data(heightmap_image)
    return create_globe(resolution, heightmap, vertical_scale)


def create_map_tile(resolution) -> GeometryData:
    geometry = GeometryData(vertex_format=VertexFormat(GlDataAttribute("uv", glm.vec2)))

    total_res = resolution + 2  # Total grid iterations including skirts

    for y in range(total_res):
        v = (y - 1) / (resolution - 1.0)

        for x in range(total_res):
            u = (x - 1) / (resolution - 1.0)

            geometry.vertices.append(Vertex(uv=glm.vec2(u, v)))

            if x != total_res - 1 and y != total_res - 1:
                vertex_index = x + y * total_res
                geometry.indices.extend([vertex_index, vertex_index + total_res + 1, vertex_index + total_res])
                geometry.indices.extend([vertex_index, vertex_index + 1, vertex_index + total_res + 1])

    return geometry


MERCATOR_MAX_LAT = math.atan(math.sinh(math.pi)) * 0.99


def create_polar_cap(rings: int, segments: int, is_north: bool, overlap_deg: float = 0.1) -> GeometryData:
    geometry = GeometryData(vertex_format=VertexFormat(GlDataAttribute("lon_lat", glm.vec2)))

    overlap_rad = math.radians(overlap_deg)

    pole_lat = math.pi / 2.0 if is_north else -math.pi / 2.0
    start_lat = (MERCATOR_MAX_LAT if is_north else -MERCATOR_MAX_LAT)

    skirt_lat = start_lat - overlap_rad if is_north else start_lat + overlap_rad

    for s in range(segments + 1):
        lon = -math.pi + (2.0 * math.pi) * (s / segments)
        geometry.vertices.append(Vertex(lon_lat=glm.vec2(lon, skirt_lat)))

    for r in range(rings + 1):
        lat = start_lat + (pole_lat - start_lat) * (r / rings)
        for s in range(segments + 1):
            lon = -math.pi + (2.0 * math.pi) * (s / segments)
            geometry.vertices.append(Vertex(lon_lat=glm.vec2(lon, lat)))

    for r in range(rings + 1):
        for s in range(segments):
            idx = r * (segments + 1) + s
            nxt_idx = idx + 1
            top_idx = idx + (segments + 1)
            top_nxt_idx = top_idx + 1

            if is_north:
                geometry.indices.extend([idx, nxt_idx, top_idx])
                geometry.indices.extend([nxt_idx, top_nxt_idx, top_idx])
            else:
                geometry.indices.extend([idx, top_idx, nxt_idx])
                geometry.indices.extend([nxt_idx, top_idx, top_nxt_idx])

    return geometry


def create_clouds(resolution) -> GeometryData:
    geometry = GeometryData(vertex_format=VertexFormat(GlDataAttribute("uv", glm.vec2)))

    for y in range(resolution):
        for x in range(resolution):
            point = glm.vec2(x, y) / (resolution - 1.0)
            geometry.vertices.append(Vertex(uv=point))
            if x != resolution - 1 and y != resolution - 1:
                vertex_index = x + y * resolution
                geometry.indices.extend([vertex_index, vertex_index + resolution + 1, vertex_index + resolution])
                geometry.indices.extend([vertex_index, vertex_index + 1, vertex_index + resolution + 1])

    return geometry
