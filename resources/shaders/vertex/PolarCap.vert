#version 430 core
layout (location = 0) in vec2 aLonLat; // Taking raw lon/lat directly

out VS_OUT {
    vec3 worldPos;
    vec4 vertexColor;
    vec2 texCoord;
    vec2 polarTexCoord;
    vec3 tangent;
    vec3 bitangent;
    vec3 normal;
    flat int isNorth;
} vs_out;

#include "common/SceneDataBuffer"
#include "common/Projection"

const float MERCATOR_MAX_LAT = atan(sinh(PI)) * 0.99;
const float DEPTH_OFFSET = 10000.0;

struct Material {
    sampler2D diffuse;
    sampler2D normalMap;
    sampler2D dataMap;
    sampler2DArray particleTexture;
    sampler2D heightmap;
};

uniform Material material;

void main() {
    vec2 uv = geoPosToUv(aLonLat);
    bool isNorth = (uv.y > 0.5);
    vec2 polarUv = geoPosToPolarUV(aLonLat, isNorth);

    float depthOffset = abs(aLonLat.y) + 0.0001 > MERCATOR_MAX_LAT ? 0 : DEPTH_OFFSET;
    float elevation = unscaleElevation(texture(material.heightmap, polarUv).r) - depthOffset;
    vec3 geoPos = vec3(aLonLat, elevation);
    vs_out.worldPos = project(geoPos, scene.projectionMode);

    gl_Position = scene.viewProjection * vec4(vs_out.worldPos, 1.0);

    vs_out.vertexColor = vec4(1.0);
    vs_out.texCoord = uv;
    vs_out.polarTexCoord = polarUv;

    vs_out.normal = vec3(cos(aLonLat.y) * sin(aLonLat.x), -cos(aLonLat.y) * cos(aLonLat.x), sin(aLonLat.y));
    vs_out.tangent = vec3(cos(aLonLat.x), sin(aLonLat.x), 0.0);
    vs_out.bitangent = cross(vs_out.normal, vs_out.tangent);

    vs_out.isNorth = isNorth ? 0 : 1;
}
