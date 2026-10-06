import hashlib
from pathlib import Path

import numpy as np

from rendering.data.gl_data_format import GlDataAttribute, VertexFormat
from rendering.data.gl_types import type_name, type_from_name
from rendering.geometry.geometry import Geometry
from rendering.geometry.geometry_data import GeometryData
from util.paths import GEOMETRY_CACHE
from util.startup import checkpoint

BASE_VERSION = 0


def _hash_params(*args, **kwargs) -> str:
    h = hashlib.sha256()
    h.update(repr(args).encode())
    h.update(repr(sorted(kwargs.items())).encode())
    return h.hexdigest()[:16]


def _cache_path(name: str, param_hash: str) -> Path:
    return GEOMETRY_CACHE / f"{name}_{param_hash}.npz"


def _serialize_vertex_format(vertex_format: VertexFormat):
    return np.array([(attr.name, type_name(attr.type)) for attr in vertex_format.attributes], dtype=object)


def _deserialize_vertex_format(data):
    return VertexFormat(*[GlDataAttribute(name=name, type=type_from_name(type_name_)) for name, type_name_ in data])


def load_geometry(
    name: str,
    generator_fn,
    *args,
    version: int = 0,
    **kwargs,
) -> Geometry:
    param_hash = _hash_params(BASE_VERSION + version, *args, **kwargs)

    path = _cache_path(name, param_hash)

    if path.exists():
        data = np.load(path, allow_pickle=True)
        vertex_array = data["vertices"]
        checkpoint()
        index_array = data["indices"]
        checkpoint()
        vertex_format = _deserialize_vertex_format(data["vertex_format"])
        base_radius = float(data["base_radius"])
        data.close()
        checkpoint()

        return Geometry(
            vertex_array=vertex_array,
            index_array=index_array,
            vertex_format=vertex_format,
            base_radius=base_radius,
        )

    geometry_data: GeometryData = generator_fn(*args, **kwargs)
    vertex_array = geometry_data.get_vertex_array()
    index_array = geometry_data.get_index_array()

    np.savez_compressed(
        path,
        vertices=vertex_array,
        indices=index_array,
        vertex_format=_serialize_vertex_format(geometry_data.vertex_format),
        base_radius=geometry_data.base_radius,
    )

    return Geometry(
        vertex_array=vertex_array,
        index_array=index_array,
        vertex_format=geometry_data.vertex_format,
        base_radius=geometry_data.base_radius,
    )
