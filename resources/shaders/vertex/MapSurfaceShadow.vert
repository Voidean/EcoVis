#version 430 core

#include "common/VertexLayout"
#include "common/SceneDataBuffer"
#include "common/Projection"

struct Instance {
    mat4 model;
    vec4 geoPos;
};

layout(std430, binding = 0) buffer InstanceData {
    Instance instances[];
};

uniform mat4 lightViewProj;
uniform dvec3 lightOrigin;

uniform float modelScale;

void main() {
    mat4 model = instances[gl_InstanceID].model;
    vec3 geoPos = instances[gl_InstanceID].geoPos.xyz;

    vec4 localPos = model * vec4(aPos, 1.0) * modelScale;
    vec3 origin = project(geoPos, scene.projectionMode);

    // --- GLOBE ALIGNMENT ---
    vec3 localUp = normalize(origin);
    vec3 worldUp = vec3(0.0, 0.0, 1.0);

    // Handle poles to prevent cross-product collapse
    if (abs(dot(localUp, worldUp)) > 0.99) {
        worldUp = vec3(0.0, 1.0, 0.0);
    }

    vec3 localRight = normalize(cross(localUp, worldUp));
    vec3 localForward = cross(localRight, localUp);
    mat3 alignRot = mat3(-localRight, localForward, localUp);

    vec3 worldPos = (alignRot * localPos.xyz) + origin;

    vec3 cascadePos = vec3(dvec3(worldPos) - lightOrigin);
    gl_Position = lightViewProj * vec4(cascadePos, 1.0);
}
