#version 430 core
layout (location = 0) in vec2 aLonLat; // Taking raw lon/lat directly

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
uniform mat4 lightViewProj;
uniform dvec3 lightOrigin;

void main() {
    vec2 uv = geoPosToUv(aLonLat);
    bool isNorth = (uv.y > 0.5);
    vec2 polarUv = geoPosToPolarUV(aLonLat, isNorth);

    float depthOffset = abs(aLonLat.y) + 0.0001 > MERCATOR_MAX_LAT ? 0 : DEPTH_OFFSET;
    float elevation = unscaleElevation(texture(material.heightmap, polarUv).r) - depthOffset;
    vec3 geoPos = vec3(aLonLat, elevation);
    vec3 worldPos = projectToGlobe(geoPos);

    vec3 cascadePos = vec3(dvec3(worldPos) - lightOrigin);
    gl_Position = lightViewProj * vec4(cascadePos, 1.0);
}
