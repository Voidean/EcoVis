#version 430 core

#include "common/VertexLayout"
#include "common/VertexOut" (dir=out)
#include "common/SceneDataBuffer"
#include "common/Projection"

struct Instance {
    mat4 model;
    vec4 geoPos;
};

layout(std430, binding = 0) buffer InstanceData {
    Instance instances[];
};

uniform float modelScale;

void main() {
    mat4 model = instances[gl_InstanceID].model;
    vec3 geoPos = instances[gl_InstanceID].geoPos.xyz;

    // Local vertex transformation (Scale/Rotation from Entity)
    vec4 localPos = model * vec4(aPos, 1.0) * modelScale;

    // Calculate Anchor Point on the map/globe
    vec3 origin = project(geoPos, scene.projectionMode);

    mat3 alignRot = mat3(1.0); // Default identity for flat maps

    if (scene.projectionMode == 0) {
        // --- GLOBE ALIGNMENT ---
        vec3 localUp = normalize(origin);
        vec3 worldUp = vec3(0.0, 0.0, 1.0);

        // Handle poles to prevent cross-product collapse
        if (abs(dot(localUp, worldUp)) > 0.99) {
            worldUp = vec3(0.0, 1.0, 0.0);
        }

        // Construct a Right-Handed Basis to prevent inverted faces.
        vec3 localRight = normalize(cross(localUp, worldUp));
        vec3 localForward = cross(localRight, localUp);

        // Construct basis matrix (Column-major)
        alignRot = mat3(-localRight, localForward, localUp);

        vs_out.worldPos = (alignRot * localPos.xyz) + origin;
    } else {
        vs_out.worldPos = localPos.xyz + origin;
    }

    gl_Position = scene.viewProjNoTrans * vec4(dvec3(vs_out.worldPos) - scene.dViewPos, 1.0);

    // Normal Transformations
    // Normals must be rotated by the same globe-alignment matrix
    mat3 combinedRot = alignRot * mat3(model);

    vs_out.tangent = normalize(combinedRot * aTangent);
    vs_out.bitangent = normalize(combinedRot * aBitangent);
    vs_out.normal = normalize(combinedRot * aNormal);

    vs_out.vertexColor = aColor;
    vs_out.texCoord = aTexCoord;
}
