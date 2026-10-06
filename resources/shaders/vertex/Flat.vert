#version 430 core

#include "common/VertexLayout"

layout (std430, binding = 0) buffer InstanceData {
    mat4 modelInstances[];
};

out VS_OUT {
    vec4 vertexColor;
    vec2 texCoord;
} vs_out;

uniform bool useInstancing;
uniform mat4 model;// used for non-instanced

#include "common/SceneDataBuffer"

void main() {
    mat4 model_ = useInstancing ? modelInstances[gl_InstanceID] : model;
    gl_Position = scene.viewProjection * model_ * vec4(aPos, 1.0);

    vs_out.vertexColor = aColor;
    vs_out.texCoord = aTexCoord;
}