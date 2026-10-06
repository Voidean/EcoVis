from provider import power_models_repository, power_metadata_repository, power_point_repository
from rendering.data.gl_data_format import ShaderBufferFormat
from rendering.drawables.culled_model_batch import CulledModelBatch
from rendering.drawables.line import LineCollection
from rendering.drawables.model import Model, EntityModel
from rendering.geometry.mesh import Mesh
from rendering.scene.scene import Scene
from rendering.shaders.compute_shader import ComputeShader
from rendering.shaders.shader import Shader
from rendering.textures.texture import Texture
from repository.globe_borders_repository import load_all_borders
from repository.globe_repository import *
from repository.power_data.geojson_sqlite_power_metadata_repository import load_power_lines
from service.geometry_cache import load_geometry
from util.config import config
from util.coordinate_constants import GLOBE_RADIUS
from util.paths import SUN_LUT
from util.power_util import create_wind_turbine_composite_structure, create_simple_composite_structure
from util.startup import checkpoint


def scene_builder():
    scene = Scene()
    checkpoint()

    # ---------- Build and Compile Shaders ----------
    yield 0.1, "Compiling Shaders..."

    shaders = {
        "skybox": Shader("Skybox", "Flat", write_depth_buffer=False, frustum_culling=False),
        "globe": Shader("MapTile", "Globe"),
        "polar_cap": Shader("PolarCap", "PolarCap"),
        "line": Shader("Line", "Line", write_depth_buffer=False),
        "standard": Shader("Standard", "Standard"),
        "cloud": Shader("Cloud", "Cloud", write_depth_buffer=False, double_sided=True),
        "surface": Shader("MapSurface", "Standard"),
        # Render overlay points last; their shader performs globe-horizon culling.
        "power_point": Shader(
            "MapPoint", "MapPoint", double_sided=True,
            write_depth_buffer=False, frustum_culling=False,
        ),
    }

    for shader_id, shader in shaders.items():
        scene.add_shader(shader_id, shader)
        checkpoint()

    shaders["standard"].default_drawable_uniforms = {
        "shadowBodyOrigin": glm.vec3(0.0),
        "shadowBodyRadius": GLOBE_RADIUS,
    }

    screen_space_shaders = {
        "atmosphere": Shader("ScreenSpace", "Atmosphere",
                             transmittance_blend=True, write_depth_buffer=False),
    }

    screen_space_shaders["atmosphere"].textures["sunLUT"] = Texture(
        np.load(SUN_LUT), repeat_s=False, repeat_t=False, mipmaps=False
    )

    for shader_id, shader in screen_space_shaders.items():
        scene.add_screen_space_shader(shader_id, shader)
        checkpoint()

    shadow_shaders = {
        "globe": Shader("MapTileShadow", "Shadow"),
        "polar_cap": Shader("PolarCapShadow", "Shadow"),
        "standard": Shader("StandardShadow", "Shadow"),
        "surface": Shader("MapSurfaceShadow", "Shadow"),
    }

    for shader_id, shader in shadow_shaders.items():
        scene.add_shadow_shader(shader_id, shader)
        checkpoint()

    # ---------- Set up Scene ----------
    scene.camera.translation = glm.dvec3(0, -2, 2) * GLOBE_RADIUS
    scene.camera.turn_to_vector(-scene.camera.translation)
    scene.camera.fov = config.graphics.default_fov

    yield 0.2, "Loading Globe Model..."



    yield 0.3, "Loading Globe Model..."

    map_tile_mesh = Mesh(create_map_tile(32))
    checkpoint()
    map_tile_mesh.textures["emissive"] = Texture.from_file("globe/emissive.jpg", repeat_t=False)
    checkpoint()

    map_tile_instance_format = ShaderBufferFormat(
        GlDataAttribute("nodePosLayer", glm.ivec4)
    )
    map_tiles = CulledModelBatch(map_tile_mesh, map_tile_instance_format, cull_shader=ComputeShader("MapTileCull"))

    scene.add_drawable("map_tiles", map_tiles, shader_id="globe")

    north_pole_textures = {
        "diffuse": Texture.from_file("globe/north_pole/diffuse.png", repeat_t=False),
        "heightmap": Texture.from_file("globe/north_pole/heightmap.png", repeat_t=False),
        "normalMap": Texture.from_file("globe/north_pole/normal.png", repeat_t=False),
    }

    north_polar_cap_mesh = Mesh(create_polar_cap(16, 64, True), north_pole_textures)
    checkpoint()
    north_polar_cap = Model(north_polar_cap_mesh)
    scene.add_drawable("north_polar_cap", north_polar_cap, shader_id="polar_cap")

    south_pole_textures = {
        "diffuse": Texture.from_file("globe/south_pole/diffuse.png", repeat_t=False),
        "heightmap": Texture.from_file("globe/south_pole/heightmap.png", repeat_t=False),
        "normalMap": Texture.from_file("globe/south_pole/normal.png", repeat_t=False),
    }

    south_polar_cap_mesh = Mesh(create_polar_cap(16, 64, False), south_pole_textures)
    checkpoint()
    south_polar_cap = Model(south_polar_cap_mesh)
    scene.add_drawable("south_polar_cap", south_polar_cap, shader_id="polar_cap")

    yield 0.5, "Loading Border Models..."

    for border_id, border in load_all_borders().items():
        scene.add_drawable(border_id, border, shader_id="line")
        checkpoint()

    yield 0.55, "Loading Cloud Models..."

    clouds_mesh = Mesh(create_clouds(128))
    checkpoint()
    clouds = Model(clouds_mesh)
    scene.add_drawable("clouds", clouds, shader_id="cloud")

    yield 0.6, "Loading Sky and Sun Models..."

    sky_mesh = Mesh(load_geometry("sky", create_sphere, 10, inverted=True))
    checkpoint()
    sky_texture = Texture.from_file("sky/diffuse.jpg", repeat_t=False)
    checkpoint()
    sky_mesh.textures["diffuse"] = sky_texture
    screen_space_shaders["atmosphere"].textures["sky"] = sky_texture

    sky = EntityModel(sky_mesh)
    sky.entity.scale *= 500

    scene.add_drawable("sky", sky, shader_id="skybox")

    sun_mesh = Mesh(load_geometry("sun", create_sphere, 10))
    checkpoint()

    sun = EntityModel(sun_mesh)
    sun.entity = scene.light_source
    sun.entity.scale *= GLOBE_RADIUS / 2.0

    scene.add_drawable("sun", sun, shader_id="skybox")

    yield 0.7, "Loading Moon Model..."

    moon_mesh = Mesh(load_geometry("moon", create_globe_from_path, 100, "moon/heightmap.png", vertical_scale=20.0))
    checkpoint()
    moon_mesh.textures["diffuse"] = Texture.from_file("moon/diffuse.tif", repeat_t=False)
    checkpoint()
    moon_mesh.textures["normalMap"] = Texture.from_file("moon/normal.png", repeat_t=False)
    checkpoint()

    moon = EntityModel(moon_mesh)
    moon.entity.scale *= 0.25
    moon.shader_uniforms = {
        "shadowBodyOrigin": lambda: glm.vec3(moon.entity.translation),
        "shadowBodyRadius": moon.get_bounding_radius(),
    }

    scene.add_drawable("moon", moon, shader_id="standard")

    yield 0.8, "Loading Power Plant Data..."

    power_repo = power_models_repository()
    power_model_cull_shader = ComputeShader("SurfaceEntityCull")
    checkpoint()

    # load models for plants
    power_repo.composite_structures["wind"] = create_wind_turbine_composite_structure(power_model_cull_shader)
    power_repo.composite_structures["hydro"] = create_simple_composite_structure("hydroelectric_dam", power_model_cull_shader, "palette.png")
    power_repo.composite_structures["PV"] = create_simple_composite_structure("solarpanel", power_model_cull_shader, "palette.png")
    power_repo.composite_structures["geothermal"] = create_simple_composite_structure("geothermal", power_model_cull_shader, "palette.png")
    power_repo.composite_structures["biomass"] = create_simple_composite_structure("biomass", power_model_cull_shader, "palette.png")
    power_repo.composite_structures["biofuel"] = create_simple_composite_structure("biofuel", power_model_cull_shader, "palette.png")
    power_repo.composite_structures["bars"] = create_simple_composite_structure("cube", power_model_cull_shader)
    # set placeholder models for plants that have no model
    power_repo.fill_empty_composite_structures(power_model_cull_shader)
    checkpoint()

    plants = power_metadata_repository().get_all_plants()
    power_repo.update_plant_models(plants=plants)
    checkpoint()

    for plant_type, structures in power_repo.composite_structures.items():
        for i, s in enumerate(structures):
            scene.add_drawable(f"power_model_{plant_type}_{i}", s.model, shader_id="surface")
            s.model.hidden = True
            if s.animation:
                scene.animateables.append(s.model)
            checkpoint()

    for plant_type, points in power_point_repository().build_collections(plants).items():
        scene.add_drawable(f"power_point_{plant_type}", points, shader_id="power_point")
        points.hidden = True
        checkpoint()

    yield 0.9, "Loading Power Grid..."

    power_grid_geometry = load_geometry(
        "power_grid",
        load_power_lines,
        "power_lines.geojson",
    )
    checkpoint()
    power_grid = LineCollection(power_grid_geometry)
    scene.add_drawable("power_grid", power_grid, shader_id="line")

    yield 1.0, "Starting..."
    return scene
