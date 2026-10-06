#version 430 core

layout(location = 0) in vec3 geoPos;

#include "common/SceneDataBuffer"
#include "common/Projection"

uniform float pointSize = 5.0;

void main() {
    vec3 worldPos = project(geoPos, scene.projectionMode);

    // Overlay points are not tested against terrain depth. Cull points whose
    // anchor lies beyond the globe horizon instead, so the far side remains hidden.
    if (scene.projectionMode == 0) {
        dvec3 surfaceNormal = normalize(dvec3(worldPos));
        if (dot(scene.dViewPos, surfaceNormal) <= double(GLOBE_RADIUS)) {
            gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
            gl_PointSize = 0.0;
            return;
        }
    }

    gl_Position = scene.viewProjNoTrans * vec4(dvec3(worldPos) - scene.dViewPos, 1.0);

    // The renderer uses a reversed depth buffer, where 1 is nearest. This keeps
    // visible points above terrain without allowing far-side points through.
    gl_Position.z = gl_Position.w;
    gl_PointSize = pointSize;
}
