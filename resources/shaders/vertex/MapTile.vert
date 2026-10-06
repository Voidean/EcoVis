#version 430 core
layout (location = 0) in vec2 aPos; // u, v pos in map tile

#include "common/GlobeVertexOut" (dir=out)
#include "common/SceneDataBuffer"
#include "common/Projection"

#include "common/MapTileBuffer"

const float BASE_DEPTH_OFFSET = 1000000.0;
const float MIN_OFFSET = 100.0;

struct Material {
    sampler2DArray diffuse;
    sampler2D emissive;
    sampler2D dataMap;
    sampler2DArray particleTexture;
    sampler2DArray heightmap;
    sampler2DArray normalMap;
};

uniform Material material;

void main() {
    vec2 pos = aPos;

    ivec3 nodePos = nodePosLayer[gl_InstanceID].xyz;
    int layerIndex = nodePosLayer[gl_InstanceID].w;

    float depthOffset = 0.0;
    if (pos.x < 0.0 || pos.x > 1.0 || pos.y < 0.0 || pos.y > 1.0) {
        pos = clamp(pos, 0.0, 1.0);
        int lodLevel = nodePos.z;
        float lodScale = exp2(-float(lodLevel));
        depthOffset = max(MIN_OFFSET, BASE_DEPTH_OFFSET * lodScale);
    }

    vec2 lonLat = vec2(quadTreeNodeToGeoPos(nodePos, pos));
    vec2 uv = geoPosToUv(lonLat);

    // float elevation = unscaleElevation(texture(material.heightmap, vec3(pos, layerIndex)).r);
    // float elevation = texture(material.heightmap, vec3(pos, layerIndex)).r * 32767.0;
    float elevation = texture(material.heightmap, vec3(pos, layerIndex)).r;
    vec3 geoPos = vec3(lonLat, elevation - depthOffset);
    vs_out.worldPos = project(geoPos, scene.projectionMode);

    gl_Position = scene.viewProjNoTrans * vec4(dvec3(vs_out.worldPos) - scene.dViewPos, 1.0);

    vs_out.vertexColor = vec4(1.0);
    vs_out.texCoord = uv;

    vs_out.normal = vec3(cos(lonLat.y) * sin(lonLat.x), -cos(lonLat.y) * cos(lonLat.x), sin(lonLat.y));

    vs_out.layerTexCoord = vec3(pos, layerIndex);
    vs_out.geoPos = geoPos;
    vs_out.nodePos = nodePos.xyz;
}
