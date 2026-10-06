#version 430 core

#include "common/VertexLayout"

layout (std430, binding = 0) buffer InstanceData {
    mat4 modelInstances[];
}; // instance model

uniform bool useInstancing;
uniform mat4 model; // used for non-instanced

#include "common/VertexOut" (dir=out)
#include "common/SceneDataBuffer"

void main() {
    mat4 model_ = useInstancing ? modelInstances[gl_InstanceID] : model;
    vec4 worldPos = model_ * vec4(aPos, 1.0);
    vs_out.worldPos = worldPos.xyz;

    gl_Position = scene.viewProjection * worldPos;
    // Assume uniform scaling
    // otherwise transpose(inverse(mat3(model))) would need to be used
    vs_out.tangent = normalize(mat3(model_) * aTangent);
    vs_out.bitangent = normalize(mat3(model_) * aBitangent);
    vs_out.normal = normalize(mat3(model_) * aNormal);

    vs_out.vertexColor = aColor;
    vs_out.texCoord = aTexCoord;
}
