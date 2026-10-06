#version 430 core

in VS_OUT {
    vec2 texCoord;
    vec3 normal;
    vec3 worldPos;
} vs_out;

out vec4 FragColor;

struct Material {
    sampler2D alpha;
};

uniform Material material;

#include "common/SceneDataBuffer"

const vec3 cloudColor = vec3(0.8, 0.8, 0.8);

#include "common/Noise"

void main() {
    float alpha = texture(material.alpha, vs_out.texCoord).r;
    if (alpha <= 0.001) {
        discard;
    }

    vec3 normal = normalize(vs_out.normal);
    float noise = fbm(normal * 25.0) * 0.5;
    float diffuse;
    if (scene.enableShadows) {
        diffuse = max(dot(normalize(normal + noise * 0.1), scene.lightDirection), 0.0);
    } else {
        diffuse = 1.0;
    }
    vec3 color = cloudColor - noise * 0.2;

    noise = noise * 0.5 + 0.5;
    alpha = smoothstep(0.0, 0.2 * noise, alpha) + smoothstep(0.2 * noise, 0.5 * noise, alpha) + smoothstep(0.5 * noise, 1.0, alpha);
    alpha = min(alpha * 0.1, 0.8);

    float distance = length(vs_out.worldPos - scene.viewPos);
    float distanceFade = smoothstep(200000.0, 300000.0, distance);

    FragColor = vec4((scene.ambient + diffuse) * color, alpha * distanceFade);
}
