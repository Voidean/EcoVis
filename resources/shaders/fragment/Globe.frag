#version 430 core

#include "common/GlobeVertexOut" (dir=in)

out vec4 FragColor;

struct Material {
    sampler2DArray diffuse;
    sampler2D emissive;
    sampler2D dataMap;
    sampler2DArray particleTexture;
    sampler2DArray heightmap;
    sampler2DArray normalMap;
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

uniform bool drawDebug = false;

#include "common/SceneDataBuffer"

const vec3  emissiveTint = vec3(1.0, 0.75, 0.5);
const float emissiveIntensity = 1.5;

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
        vec3 normal = normalize(texture(material.normalMap, vs_out.layerTexCoord).xyz * 2.0 - 1.0);

        float diffuse = max(dot(normal, scene.lightDirection), 0.0);
        float emissiveStrength = -min(dot(normalize(vs_out.normal), scene.lightDirection), 0.0);

        vec4 color = vec4(texture(material.diffuse, vs_out.layerTexCoord).rgb, 1.0) * vs_out.vertexColor;
        vec3 emissive = vec3(texture(material.emissive, vs_out.texCoord).r) * emissiveTint * emissiveIntensity;
        float lighting = scene.ambient + (diffuse * (1.0 - castShadow()));

        FragColor = vec4(lighting * color.rgb + emissiveStrength * emissive, color.a);
    } else {
        FragColor = vec4(texture(material.diffuse, vs_out.layerTexCoord).rgb, 1.0) * vs_out.vertexColor;
    }
    if (showWind) {
        float windValue = 0.0;
        windValue = texture(material.particleTexture, vs_out.layerTexCoord).r; // todo geo constrain??
        FragColor = vec4(FragColor.rgb * (1 - windValue) + vec3(1.0) * windValue, FragColor.a);
    }
    if (drawDebug) {
        if (vs_out.layerTexCoord.x < 0.01 || vs_out.layerTexCoord.x > 0.99 ||
            vs_out.layerTexCoord.y < 0.01 || vs_out.layerTexCoord.y > 0.99) {
            FragColor = vec4(1.0, 1.0, 0.0, 1.0);
        }
    }
}
