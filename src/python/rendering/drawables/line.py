from OpenGL.GL import *
from pyglm import glm

from rendering.geometry.geometry import Geometry
from rendering.geometry.geometry_data import GeometryData
from rendering.drawables.drawable import Drawable
from util.coordinate_constants import GLOBE_RADIUS
from util.culling import cull_frustum


class LineCollection(Drawable):
    def __init__(self, geometry: Geometry | GeometryData,
                 color=glm.vec4(1.0), dashed=False, dash_size=0.002, gap_size=0.001):
        super().__init__()
        self.geometry = Geometry.from_data(geometry)

        self.color = color
        self.dashed = dashed
        self.dash_size = dash_size
        self.gap_size = gap_size

        self.shader_uniforms = {
            "lineColor": lambda: self.color,
            "dashed": lambda: self.dashed,
            "dashSize": lambda: self.dash_size,
            "gapSize": lambda: self.gap_size,
        }

    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        if enable_culling and cull_frustum(frustum_planes, glm.vec3(0), 1.1 * GLOBE_RADIUS): return

        self.geometry.use()
        self.geometry.draw(GL_LINE_STRIP)

    def delete(self):
        self.geometry.delete()
