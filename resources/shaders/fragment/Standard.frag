#version 430 core

#include "common/VertexOut" (dir=in)

out vec4 FragColor;

struct Material {
    sampler2D diffuse;
    sampler2D normalMap;
};

uniform Material material;
uniform vec3 shadowBodyOrigin = vec3(0.0);
uniform float shadowBodyRadius = 6371000.0;

#include "common/SceneDataBuffer"
#include "common/NormalMap"
#include "common/ShadowCasting"

void main() {
    vec4 color = texture(material.diffuse, vs_out.texCoord) * vs_out.vertexColor;

    if (scene.enableShadows) {
        float diffuse = max(dot(normalMap(), scene.lightDirection), 0.0);
        float lighting = scene.ambient + (diffuse * (1.0 - castShadow(shadowBodyOrigin, shadowBodyRadius)));

        FragColor = vec4(lighting * color.rgb, color.a);
    } else {
        FragColor = color;
    }
}
