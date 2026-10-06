from typing import Iterable

import numpy as np
from pyglm import glm

from rendering.data.gl_data_format import GlDataAttribute, VertexFormat, Vertex

RESTART_INDEX = 99999999

DEFAULT_VERTEX_FORMAT = VertexFormat(
    GlDataAttribute("position", glm.vec3),
    GlDataAttribute("tangent", glm.vec3, glm.vec3(1, 0, 0)),
    GlDataAttribute("bitangent", glm.vec3, glm.vec3(0, 1, 0)),
    GlDataAttribute("normal", glm.vec3, glm.vec3(0, 0, 1)),
    GlDataAttribute("color", glm.vec4, glm.vec4(1, 1, 1, 1)),
    GlDataAttribute("uv", glm.vec2),
)
LINE_VERTEX_FORMAT = VertexFormat(
    GlDataAttribute("position", glm.vec4),
)


class GeometryData:
    def __init__(self, vertices: Iterable[Vertex] | None = None, indices: Iterable[int] | None = None,
                 vertex_format: VertexFormat = DEFAULT_VERTEX_FORMAT):
        self.vertices = list(vertices) if vertices is not None else []
        self.indices = list(indices) if indices is not None else []
        self.vertex_format = vertex_format

    def get_vertex_array(self):
        if not self.vertices: return np.array([], dtype=np.uint8)

        stride = self.vertex_format.stride_bytes
        vertex_bytes = bytearray(stride * len(self.vertices))

        for i, vertex in enumerate(self.vertices):
            vertex_bytes[i * stride: (i + 1) * stride] = self.vertex_format.serialize(vertex)

        return np.frombuffer(bytes(vertex_bytes), dtype=np.uint8)

    def get_index_array(self):
        return np.array(self.indices, dtype=np.uint32)

    @property
    def base_radius(self):
        pos_attr = self.vertex_format.get_attribute("position")
        if not pos_attr or not self.vertices: return None

        return max([glm.length(vert.get_value(pos_attr)) for vert in self.vertices])

    def generate_normals_and_tangents(self):
        # Reset normals, tangents, and bitangents
        for v in self.vertices:
            v.normal = glm.vec3(0, 0, 0)
            v.tangent = glm.vec3(0, 0, 0)
            v.bitangent = glm.vec3(0, 0, 0)

        # Process each triangle
        for i in range(0, len(self.indices), 3):
            v0 = self.vertices[self.indices[i]]
            v1 = self.vertices[self.indices[i + 1]]
            v2 = self.vertices[self.indices[i + 2]]

            p0, p1, p2 = v0.position, v1.position, v2.position
            uv0, uv1, uv2 = v0.uv, v1.uv, v2.uv

            # --- NORMAL ---
            edge1 = p1 - p0
            edge2 = p2 - p0
            face_normal = glm.normalize(glm.cross(edge1, edge2))

            v0.normal += face_normal
            v1.normal += face_normal
            v2.normal += face_normal

            # --- TANGENT & BITANGENT ---
            deltaUV1 = uv1 - uv0
            deltaUV2 = uv2 - uv0

            r = deltaUV1.x * deltaUV2.y - deltaUV1.y * deltaUV2.x
            if abs(r) < 1e-8:
                continue
            r = 1.0 / r

            tangent = (edge1 * deltaUV2.y - edge2 * deltaUV1.y) * r
            bitangent = (edge2 * deltaUV1.x - edge1 * deltaUV2.x) * r

            v0.tangent += tangent
            v1.tangent += tangent
            v2.tangent += tangent

            v0.bitangent += bitangent
            v1.bitangent += bitangent
            v2.bitangent += bitangent

        # Normalize and orthogonalize per vertex
        for v in self.vertices:
            # Normalize normal
            if glm.length(v.normal) > 0:
                v.normal = glm.normalize(v.normal)
            else:
                v.normal = glm.vec3(0, 1, 0)

            # Orthogonalize tangent
            t = v.tangent
            if glm.length(t) == 0:
                t = glm.vec3(1, 0, 0)

            v.tangent = glm.normalize(t - v.normal * glm.dot(v.normal, t))

            # Recalculate bitangent to ensure orthogonality
            v.bitangent = glm.normalize(glm.cross(v.normal, v.tangent))
