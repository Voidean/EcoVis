#version 430 core
layout (location = 0) in vec4 aPosDist; // Lon, Lat in radians

out float vDist;

#include "common/SceneDataBuffer"

const float worldOffset = 5000.0;

#include "common/Projection"

void main() {
    vec3 pos = project(aPosDist.xyz, scene.projectionMode);
    vec4 viewPos = scene.view * vec4(pos, 1.0);

    gl_Position = scene.projection * viewPos;

    // Prevent z-fighting by subtracting a bit from the screen-space depth
    float biasedZView = viewPos.z + worldOffset;
    float biasedZClip = (scene.projection[2][2] * biasedZView) + scene.projection[3][2];
    gl_Position.z = (biasedZClip / -biasedZView) * gl_Position.w;

    vDist = aPosDist.w;
}