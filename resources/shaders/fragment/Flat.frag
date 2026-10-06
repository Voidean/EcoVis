#version 430 core
in VS_OUT {
    vec4 vertexColor;
    vec2 texCoord;
} vs_out;

out vec4 FragColor;

struct Material {
    sampler2D diffuse;
};

uniform Material material;

void main() {
    FragColor = texture(material.diffuse, vs_out.texCoord) * vs_out.vertexColor;
}