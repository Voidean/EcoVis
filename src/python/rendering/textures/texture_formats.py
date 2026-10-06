import numpy as np
from OpenGL.GL import *

NUMPY_TO_GL_FORMATS = {
    np.float16: GL_HALF_FLOAT,
    np.float32: GL_FLOAT,
    np.float64: GL_DOUBLE,
    np.uint8  : GL_UNSIGNED_BYTE,
    np.uint16 : GL_UNSIGNED_SHORT,
    np.uint32 : GL_UNSIGNED_INT,
    np.uint64 : GL_UNSIGNED_INT64,
    np.int8   : GL_BYTE,
    np.int16  : GL_SHORT,
    np.int32  : GL_INT,

}


def numpy_to_gl_format(dtype):
    for np_type, gl_type in NUMPY_TO_GL_FORMATS.items():
        if np.issubdtype(dtype, np_type): return gl_type
    raise ValueError(f"Unsupported data type: {dtype}")


GL_FORMAT_BYTE_SIZES = {
    GL_HALF_FLOAT    : 2,
    GL_FLOAT         : 4,
    GL_DOUBLE        : 8,
    GL_UNSIGNED_BYTE : 1,
    GL_UNSIGNED_SHORT: 2,
    GL_UNSIGNED_INT  : 4,
    GL_UNSIGNED_INT64: 8,
    GL_BYTE          : 1,
    GL_SHORT         : 2,
    GL_INT           : 4,

}

COLOR_INTERNAL_FORMATS = {
    GL_HALF_FLOAT    : {1: GL_R16F, 2: GL_RG16F, 3: GL_RGB16F, 4: GL_RGBA16F},
    GL_FLOAT         : {1: GL_R32F, 2: GL_RG32F, 3: GL_RGB32F, 4: GL_RGBA32F},
    GL_UNSIGNED_BYTE : {1: GL_R8,   2: GL_RG8,   3: GL_RGB8,   4: GL_RGBA8  },
    GL_UNSIGNED_SHORT: {1: GL_R16,  2: GL_RG16,  3: GL_RGB16,  4: GL_RGBA16 },
    GL_BYTE          : {1: GL_R8_SNORM,  2: GL_RG8_SNORM,  3: GL_RGB8_SNORM,  4: GL_RGBA8_SNORM },
    GL_SHORT         : {1: GL_R16_SNORM, 2: GL_RG16_SNORM, 3: GL_RGB16_SNORM, 4: GL_RGBA16_SNORM},
}

COLOR_FORMATS = {1 : GL_RED, 2 : GL_RG, 3 : GL_RGB, 4 : GL_RGBA}

GL_TO_GLSL_FORMAT = {
    GL_RGBA8: "rgba8",
    GL_R32F: "r32f",
    GL_RG32F: "rg32f",
    GL_RGBA32F: "rgba32f",
    GL_R16F: "r16f",
    GL_RGBA16F: "rgba16f",
    GL_R8: "r8"
}
