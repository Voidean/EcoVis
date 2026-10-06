#version 430 core

#include "common/ParticleBuffer" (BINDING=0)

layout(std430, binding = 2) readonly buffer ActiveIndices {
    uint particleIndices[];
};

out vec2 vGlobalPos;

void main() {
    uint lineIdx = gl_VertexID / 2;
    bool isEndPoint = (gl_VertexID % 2 == 1);
    Particle p = particles[particleIndices[lineIdx]];
    vGlobalPos = isEndPoint ? p.pos : p.lastPos;
}