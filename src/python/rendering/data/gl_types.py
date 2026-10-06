from dataclasses import dataclass
from typing import Callable

from rendering.data.gl_uniform_upload import *


@dataclass(frozen=True)
class GLTypeInfo:
    name: str
    py_type: type
    size_bytes: int
    component_count: int
    align_140: int
    align_430: int

    uniform_setter: Callable | None = None
    uniform_array_setter: Callable | None = None

    is_matrix: bool = False
    cols: int = 1
    col_type: type = None


GL_TYPES = {
    bool: GLTypeInfo("bool", bool, 4, 1, 4, 4, upload_bool, upload_bool_array),
    float: GLTypeInfo("float", float, 4, 1, 4, 4, upload_float, upload_float_array),
    int: GLTypeInfo("int", int, 4, 1, 4, 4, upload_int, upload_int_array),

    glm.vec2: GLTypeInfo("vec2", glm.vec2, 8, 2, 8, 8, upload_vec2, upload_vec2_array),
    glm.vec3: GLTypeInfo("vec3", glm.vec3, 12, 3, 16, 16, upload_vec3, upload_vec3_array),
    glm.vec4: GLTypeInfo("vec4", glm.vec4, 16, 4, 16, 16, upload_vec4, upload_vec4_array),

    glm.dvec2: GLTypeInfo("dvec2", glm.dvec2, 16, 2, 16, 16, upload_dvec2, upload_dvec2_array),
    glm.dvec3: GLTypeInfo("dvec3", glm.dvec3, 24, 3, 32, 32, upload_dvec3, upload_dvec3_array),
    glm.dvec4: GLTypeInfo("dvec4", glm.dvec4, 32, 4, 32, 32, upload_dvec4, upload_dvec4_array),

    glm.ivec2: GLTypeInfo("ivec2", glm.ivec2, 8, 2, 8, 8, upload_ivec2, upload_ivec2_array),
    glm.ivec3: GLTypeInfo("ivec3", glm.ivec3, 12, 3, 16, 16, upload_ivec3, upload_ivec3_array),
    glm.ivec4: GLTypeInfo("ivec4", glm.ivec4, 16, 4, 16, 16, upload_ivec4, upload_ivec4_array),

    glm.mat2: GLTypeInfo(
        "mat2", glm.mat2,
        16, 2, 16, 8,
        upload_mat2,
        upload_mat2_array,
        is_matrix=True,
        cols=2,
        col_type=glm.vec2,
    ),
    glm.mat3: GLTypeInfo(
        "mat3", glm.mat3,
        36, 3, 16, 16,
        upload_mat3,
        upload_mat3_array,
        is_matrix=True,
        cols=3,
        col_type=glm.vec3,
    ),
    glm.mat4: GLTypeInfo(
        "mat4", glm.mat4,
        64, 4, 16, 16,
        upload_mat4,
        upload_mat4_array,
        is_matrix=True,
        cols=4,
        col_type=glm.vec4,
    ),

    glm.dmat2: GLTypeInfo(
        "dmat2", glm.dmat2,
        32, 2, 16, 16,
        upload_dmat2,
        upload_dmat2_array,
        is_matrix=True,
        cols=2,
        col_type=glm.dvec2,
    ),
    glm.dmat3: GLTypeInfo(
        "dmat3", glm.dmat3,
        72, 3, 32, 32,
        upload_dmat3,
        upload_dmat3_array,
        is_matrix=True,
        cols=3,
        col_type=glm.dvec3,
    ),
    glm.dmat4: GLTypeInfo(
        "dmat4", glm.dmat4,
        128, 4, 32, 32,
        upload_dmat4,
        upload_dmat4_array,
        is_matrix=True,
        cols=4,
        col_type=glm.dvec4,
    ),
}

NAME_TO_TYPE = {info.name: typ for typ, info in GL_TYPES.items()}

TYPE_TO_NAME = {typ: info.name for typ, info in GL_TYPES.items()}


def align_offset(offset: int, alignment: int) -> int:
    """Rounds the offset up to the nearest multiple of the alignment."""
    return (offset + alignment - 1) & ~(alignment - 1)


def size_of(type_):
    return GL_TYPES[type_].size_bytes


def component_count(type_):
    return GL_TYPES[type_].component_count


def type_name(type_):
    return TYPE_TO_NAME[type_]


def type_from_name(name):
    return NAME_TO_TYPE[name]


def zero_of(type_):
    if type_ is bool:
        return False
    if type_ is int:
        return 0
    if type_ is float:
        return 0.0

    return type_()
