import os

import numpy as np
import trimesh
from PIL import Image
from pyglm import glm
from trimesh.visual.material import SimpleMaterial

from rendering.data.gl_data_format import Vertex
from rendering.geometry.geometry_data import GeometryData
from rendering.geometry.mesh import Mesh
from rendering.textures.texture import Texture
from util.paths import MODELS


def mesh_from_file(model_name) -> Mesh:
    """
    Load a mesh from a 3D model file using trimesh (supports .obj, .stl, .glb, etc.)
    and convert it to the vertex/index format expected by the Mesh class.
    """
    mesh = trimesh.load_mesh(MODELS / model_name / f"{model_name}.obj")

    # Handle scene (multiple submeshes)
    if isinstance(mesh, trimesh.Scene):
        combined = trimesh.util.concatenate(mesh.geometry.values())
        mesh = combined

    vertices = []
    for i in range(len(mesh.vertices)):
        # Position
        pos = glm.vec3(mesh.vertices[i])

        # Color: use vertex colors if available, otherwise default
        if mesh.visual.kind == 'vertex' and hasattr(mesh.visual, 'vertex_colors'):
            color = glm.vec4(mesh.visual.vertex_colors[i][:4] / 255.0)
        else:
            color = None

        # UV: if available
        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            uv = glm.vec2(mesh.visual.uv[i])
        else:
            uv = None

        vertices.append(Vertex(position=pos, color=color, uv=uv))

    indices = mesh.faces.flatten()

    textures = load_textures(mesh, model_name)

    geometry_data = GeometryData(vertices, indices)
    geometry_data.generate_normals_and_tangents()

    return Mesh(geometry_data, textures)


def load_textures(mesh, model_name):
    textures = {
        "diffuse": Texture.empty(),
        "normalMap": Texture.empty_normal(),
    }

    if not hasattr(mesh.visual, "material"): return None

    material = mesh.visual.material
    if isinstance(material, SimpleMaterial):
        if getattr(material, "image", None) is not None:
            textures["diffuse"] = Texture.from_image(material.image)
        elif getattr(material, "diffuse", None) is not None:
            color = np.array(material.diffuse, dtype=np.float32)
            img = Image.new("RGBA", (1, 1), tuple((color * 255).astype(int)))
            textures["diffuse"] = Texture.from_image(img)

    # Attempt to load textures by conventional names
    texture_files = {
        "normalMap": ["normal.jpg", "norm.jpg", "normal.png"],
        "specular": ["specular.jpg"],
        "roughness": ["roughness.jpg", "roughness.png", "rough.jpg"],
        "ao": ["ao.jpg", "ao.png", "ambientocclusion.jpg"]
    }

    for key, filenames in texture_files.items():
        for filename in filenames:
            path = MODELS / model_name / filename
            tex = Texture.from_image(Image.open(path)) if os.path.exists(path) else None
            if tex:
                textures[key] = tex
                break

    return textures
