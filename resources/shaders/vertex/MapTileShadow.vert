#version 430 core
layout (location = 0) in vec2 aPos; // u, v pos in map tile

#include "common/SceneDataBuffer"
#include "common/Projection"

#include "common/MapTileBuffer"

struct Material {
    sampler2DArray diffuse;
    sampler2D emissive;
    sampler2D dataMap;
    sampler2DArray particleTexture;
    sampler2DArray heightmap;
    sampler2DArray normalMap;
};

uniform Material material;
uniform mat4 lightViewProj;
uniform dvec3 lightOrigin;

void main() {
    vec2 pos = clamp(aPos, 0.0, 1.0);
    ivec3 nodePos = nodePosLayer[gl_InstanceID].xyz;
    int layerIndex = nodePosLayer[gl_InstanceID].w;

    float elevation = texture(material.heightmap, vec3(pos, layerIndex)).r;
    vec3 geoPos = vec3(quadTreeNodeToGeoPos(nodePos, pos), elevation);
    vec3 worldPos = projectToGlobe(geoPos);

    vec3 cascadePos = vec3(dvec3(worldPos) - lightOrigin);
    gl_Position = lightViewProj * vec4(cascadePos, 1.0);
}
