#version 430 core

layout (location = 0) in vec2 aPos; // u, v pos in map tile

out VS_OUT {
    vec2 texCoord;
    vec3 normal;
    vec3 worldPos;
} vs_out;

#include "common/SceneDataBuffer"
#include "common/Projection"

const float CLOUD_HEIGHT = 5000.0;

void main() {
    vec3 geoPos = vec3(uvToGeoPos(aPos), CLOUD_HEIGHT);
    vs_out.worldPos = project(geoPos, scene.projectionMode);
    gl_Position = scene.viewProjection * vec4(vs_out.worldPos, 1.0);
    vs_out.normal = vec3(cos(geoPos.y) * sin(geoPos.x), -cos(geoPos.y) * cos(geoPos.x), sin(geoPos.y));
    vs_out.texCoord = aPos;
}
