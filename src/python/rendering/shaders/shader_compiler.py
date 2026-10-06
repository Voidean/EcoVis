import re

from OpenGL.GL import *

from util.paths import SHADERS
from rendering.shaders.shader_error import ShaderCompilationError, ShaderPreprocessingError


def load_and_compile(shader_name, shader_type, defines=None):
    if shader_type == GL_VERTEX_SHADER:
        path = SHADERS / "vertex" / (shader_name + ".vert")
    elif shader_type == GL_FRAGMENT_SHADER:
        path = SHADERS / "fragment" / (shader_name + ".frag")
    elif shader_type == GL_GEOMETRY_SHADER:
        path = SHADERS / "geometry" / (shader_name + ".geom")
    elif shader_type == GL_COMPUTE_SHADER:
        path = SHADERS / "compute" / (shader_name + ".comp")
    else:
        raise NotImplementedError

    source = load_shader_source(path)
    source, _ = apply_args(source, defines)
    source = preprocess(source)

    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)

    success = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not success:
        log = glGetShaderInfoLog(shader).decode()
        raise ShaderCompilationError(path, shader_type, source, log)
    return shader


def load_shader_source(path):
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        raise FileNotFoundError(f"Shader not found: {path}\n{e}")

INCLUDE_REGEX = re.compile(r'^\s*#include\s+"([^"]+)"\s*(?:\(\s*(.*?)\s*\))?', re.MULTILINE)
DEFINE_REGEX = re.compile(r'^\s*#define\s+(\w+)(?:\s+(.*?))?$', re.MULTILINE)

def parse_args(arg_string):
    if not arg_string: return {}

    args = {}
    for pair in arg_string.split(","):
        key, value = pair.split("=", 1)
        args[key.strip()] = value.strip()
    return args


def apply_args(source, args):
    args = args or {}
    used = set()
    defined = []

    def replace(match):
        name = match.group(1)
        defined.append(name)

        if name not in args:
            return match.group(0)

        used.add(name)
        return f"#define {name} {args[name]}"

    source = DEFINE_REGEX.sub(replace, source)

    unknown = args.keys() - used
    if unknown: raise ShaderPreprocessingError(f"Unknown include arguments: {', '.join(unknown)}")

    return source, defined


def preprocess(source, included_files=None):
    if included_files is None: included_files = set()

    def replace_include(match):
        full_path = SHADERS / (match.group(1) + ".glsl")
        args = parse_args(match.group(2))

        # Prevent double includes
        key = (full_path, tuple(sorted(args.items())))
        if key in included_files: return ""
        included_files.add(key)

        included_source = load_shader_source(full_path)
        included_source, defined = apply_args(included_source, args)
        included_source = preprocess(included_source, included_files)
        included_source += "\n" + "\n".join(f"#undef {name}" for name in defined) + "\n"
        return included_source

    return INCLUDE_REGEX.sub(replace_include, source)
