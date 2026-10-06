#version 430 core

in VS_OUT {
    vec3 worldPos;
    vec4 vertexColor;
    vec2 texCoord;
    vec2 polarTexCoord;
    vec3 tangent;
    vec3 bitangent;
    vec3 normal;
    flat int isNorth;
} vs_out;

out vec4 FragColor;

struct Material {
    sampler2D diffuse;
    sampler2D normalMap;
    sampler2D dataMap;
    sampler2DArray particleTexture;
    sampler2D heightmap;
};

uniform Material material;
uniform sampler2D gradient;

uniform bool useData;
uniform bool showWind;

uniform float scaleStart = 0.0;
uniform float scaleEnd = 1.0;

uniform bool useDataRange = false;       // Toggle the range limiting
uniform vec2 dataStart = vec2(0.0, 0.0); // x = longitude min, y = latitude min
uniform vec2 dataEnd = vec2(1.0, 1.0);   // x = longitude max, y = latitude max

#include "common/SceneDataBuffer"

const vec3  emissiveTint = vec3(1.0, 0.75, 0.5);
const float emissiveIntensity = 1.5;

#include "common/NormalMap"
#include "common/ShadowCasting"

float scale(float value, float start, float end) {
    return (value - start) / (end - start);
}

vec3 getMappedUV() {
    if (!useDataRange) return vec3(vs_out.texCoord, 1.0);

    float u = fract(vs_out.texCoord.x);
    float v = vs_out.texCoord.y;

    float uScaled = -1.0;
    if (dataStart.s <= dataEnd.s) {
        // Standard Case
        uScaled = scale(u, dataStart.s, dataEnd.s);
    } else {
        // Wrap-around Case (e.g., 0.8 to 0.2)
        float span = (1.0 - dataStart.s) + dataEnd.s;
        if (u >= dataStart.s) {
            uScaled = (u - dataStart.s) / span;
        } else if (u <= dataEnd.s) {
            uScaled = (1.0 - dataStart.s + u) / span;
        }
    }

    float vScaled = scale(v, dataStart.t, dataEnd.t);

    float mask = (uScaled >= 0.0 && uScaled <= 1.0 && vScaled >= 0.0 && vScaled <= 1.0) ? 1.0 : 0.0;
    return vec3(uScaled, vScaled, mask);
}

void main() {
    vec3 mapped = getMappedUV();
    vec2 mappedUV = mapped.xy;
    bool masked = mapped.z < 0.5;

    if (useData) {
        float dataValue = 0.0;
        if (!masked) dataValue = texture(material.dataMap, mappedUV).r;

        if (abs(scaleEnd - scaleStart) > 0.0001) {
            dataValue = scale(dataValue, scaleStart, scaleEnd);
        }

        dataValue = max(0.0, min(dataValue, 1.0));

        FragColor = texture(gradient, vec2(dataValue, 0));
    } else if (scene.enableShadows) {
        float diffuse = max(dot(normalMap(vs_out.polarTexCoord), scene.lightDirection), 0.0);
        float lighting = scene.ambient + (diffuse * (1.0 - castShadow()));

        vec4 color = texture(material.diffuse, vs_out.polarTexCoord) * vs_out.vertexColor;
        FragColor = vec4(lighting * color.rgb, color.a);
    } else {
        FragColor = texture(material.diffuse, vs_out.polarTexCoord) * vs_out.vertexColor;
    }
    if (showWind) {
        float windValue = 0.0;
        if (!masked) windValue = texture(material.particleTexture, vec3(vs_out.polarTexCoord, vs_out.isNorth)).r; // todo geo constrain??
        FragColor = vec4(FragColor.rgb * (1 - windValue) + vec3(1.0) * windValue, FragColor.a);
    }
}
