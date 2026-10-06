from OpenGL.GL import GL_POINTS
from pyglm import glm

from rendering.drawables.drawable import Drawable
from rendering.geometry.geometry import Geometry
from rendering.geometry.geometry_data import GeometryData


class PointCollection(Drawable):
    """Renders a collection of screen-space points in a single draw call."""

    def __init__(
            self,
            geometry: Geometry | GeometryData,
            color=glm.vec4(1.0),
            point_size: float = 5.0,
    ):
        super().__init__()
        self.geometry = Geometry.from_data(geometry)
        self.color = color
        self.point_size = point_size
        self.shader_uniforms = {
            "pointColor": lambda: self.color,
            "pointSize": lambda: self.point_size,
        }

    def draw(self, shader, enable_culling=False, frustum_planes=None, cull_view_pos=None):
        self.geometry.use()
        self.geometry.draw(GL_POINTS)

    def delete(self):
        self.geometry.delete()
