from OpenGL.GL import *
import numpy as np
from pyglm import glm


def _array(values, dtype, components: int | None = None):
    if values is None:
        return np.ascontiguousarray([], dtype=dtype)

    if hasattr(values, "to_list"):
        values = values.to_list()
    else:
        values = [v.to_list() if hasattr(v, "to_list") else v for v in values]

    arr = np.ascontiguousarray(np.asarray(values, dtype=dtype))
    if components is not None:
        arr = arr.reshape(-1, components)
    return arr


def _matrix_array(values, dtype, rows: int, cols: int):
    if values is None:
        return np.ascontiguousarray([], dtype=dtype)

    values = [v.to_list() if hasattr(v, "to_list") else v for v in values]
    return np.ascontiguousarray(np.asarray(values, dtype=dtype).reshape(-1, rows, cols))


def upload_bool(location: int, value: bool):
    glUniform1i(location, value)


def upload_int(location: int, value: int):
    glUniform1i(location, value)


def upload_float(location: int, value: float):
    glUniform1f(location, value)


def upload_vec2(location: int, value: glm.vec2):
    glUniform2f(location, *value)


def upload_vec3(location: int, value: glm.vec3):
    glUniform3f(location, *value)


def upload_vec4(location: int, value: glm.vec4):
    glUniform4f(location, *value)


def upload_dvec2(location: int, value: glm.dvec2):
    glUniform2d(location, *value)


def upload_dvec3(location: int, value: glm.dvec3):
    glUniform3d(location, *value)


def upload_dvec4(location: int, value: glm.dvec4):
    glUniform4d(location, *value)


def upload_ivec2(location: int, value: glm.ivec2):
    glUniform2i(location, *value)


def upload_ivec3(location: int, value: glm.ivec3):
    glUniform3i(location, *value)


def upload_ivec4(location: int, value: glm.ivec4):
    glUniform4i(location, *value)


def upload_mat2(location: int, value: glm.mat2):
    glUniformMatrix2fv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_mat3(location: int, value: glm.mat3):
    glUniformMatrix3fv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_mat4(location: int, value: glm.mat4):
    glUniformMatrix4fv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_dmat2(location: int, value: glm.dmat2):
    glUniformMatrix2dv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_dmat3(location: int, value: glm.dmat3):
    glUniformMatrix3dv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_dmat4(location: int, value: glm.dmat4):
    glUniformMatrix4dv(location, 1, GL_FALSE, glm.value_ptr(value))


def upload_bool_array(location: int, values):
    arr = _array(values, np.int32)
    glUniform1iv(location, len(arr), arr)


def upload_int_array(location: int, values):
    arr = _array(values, np.int32)
    glUniform1iv(location, len(arr), arr)


def upload_float_array(location: int, values):
    arr = _array(values, np.float32)
    glUniform1fv(location, len(arr), arr)


def upload_vec2_array(location: int, values):
    arr = _array(values, np.float32, 2)
    glUniform2fv(location, len(arr), arr)


def upload_vec3_array(location: int, values):
    arr = _array(values, np.float32, 3)
    glUniform3fv(location, len(arr), arr)


def upload_vec4_array(location: int, values):
    arr = _array(values, np.float32, 4)
    glUniform4fv(location, len(arr), arr)


def upload_dvec2_array(location: int, values):
    arr = _array(values, np.float64, 2)
    glUniform2dv(location, len(arr), arr)


def upload_dvec3_array(location: int, values):
    arr = _array(values, np.float64, 3)
    glUniform3dv(location, len(arr), arr)


def upload_dvec4_array(location: int, values):
    arr = _array(values, np.float64, 4)
    glUniform4dv(location, len(arr), arr)


def upload_ivec2_array(location: int, values):
    arr = _array(values, np.int32, 2)
    glUniform2iv(location, len(arr), arr)


def upload_ivec3_array(location: int, values):
    arr = _array(values, np.int32, 3)
    glUniform3iv(location, len(arr), arr)


def upload_ivec4_array(location: int, values):
    arr = _array(values, np.int32, 4)
    glUniform4iv(location, len(arr), arr)


def upload_mat2_array(location: int, values):
    arr = _matrix_array(values, np.float32, 2, 2)
    glUniformMatrix2fv(location, len(arr), GL_FALSE, arr)


def upload_mat3_array(location: int, values):
    arr = _matrix_array(values, np.float32, 3, 3)
    glUniformMatrix3fv(location, len(arr), GL_FALSE, arr)


def upload_mat4_array(location: int, values):
    arr = _matrix_array(values, np.float32, 4, 4)
    glUniformMatrix4fv(location, len(arr), GL_FALSE, arr)


def upload_dmat2_array(location: int, values):
    arr = _matrix_array(values, np.float64, 2, 2)
    glUniformMatrix2dv(location, len(arr), GL_FALSE, arr)


def upload_dmat3_array(location: int, values):
    arr = _matrix_array(values, np.float64, 3, 3)
    glUniformMatrix3dv(location, len(arr), GL_FALSE, arr)


def upload_dmat4_array(location: int, values):
    arr = _matrix_array(values, np.float64, 4, 4)
    glUniformMatrix4dv(location, len(arr), GL_FALSE, arr)
