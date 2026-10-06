#version 430 core

#include "common/VertexLayout"

layout (std430, binding = 0) buffer InstanceData {
    mat4 modelInstances[];
}; // instance model

uniform bool useInstancing;
uniform mat4 model; // used for non-instanced
uniform mat4 lightViewProj;
uniform dvec3 lightOrigin;

#include "common/SceneDataBuffer"

void main() {
    mat4 model_ = useInstancing ? modelInstances[gl_InstanceID] : model;
    vec3 worldPos = vec3(model_ * vec4(aPos, 1.0));
    vec3 cascadePos = vec3(dvec3(worldPos) - lightOrigin);
    gl_Position = lightViewProj * vec4(cascadePos, 1.0);
}
