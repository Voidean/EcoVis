uniform sampler2DArray shadowMapArray;

// globePos is still a 32-bit vec3. At planetary scale its rounding error
// is approximately radius * FLT_EPSILON. Cover independent caster and
// receiver rounding, with a 0.5 m minimum near the world origin.
const float floatEpsilon = 1.1920929e-7;

#include "common/Projection"

float simpleShadow(vec3 bodyPos, vec3 sunDirection) {
    return 1.0 - smoothstep(-0.5, 0.0, dot(normalize(bodyPos), sunDirection));
}

float castShadow(vec3 bodyOrigin, float bodyRadius) {
    vec3 globePos;
    if (scene.projectionMode == 0) {
        globePos = vs_out.worldPos;
    } else {
        globePos = projectToGlobe(unproject(vs_out.worldPos, scene.projectionMode));
    }

    vec3 bodyPos = globePos - bodyOrigin;

    // Prevent lighting from below the spherical body. This is independent of
    // the finite cascade range and works for bodies not centered at the origin.
    vec3 sunDirection = normalize(scene.lightDirection);
    if (scene.cascadeCount == 0) {
        return simpleShadow(bodyPos, sunDirection);
    }

    float sunwardDistance = dot(bodyPos, sunDirection);
    float shadowAxisDistance = length(cross(bodyPos, sunDirection));
    if (sunwardDistance < 0.0 && shadowAxisDistance < bodyRadius) {
        return 1.0;
    }

    // todo: fix this for non globe projections, lighting should work as if it were globe, even if it is not
    vec4 viewPos = scene.view * vec4(globePos, 1.0);
    float viewSpaceDepth = abs(viewPos.z);

    // Find the correct cascade layer
    int layer = -1;
    for (int i = 0; i < scene.cascadeCount; ++i) {
        if (viewSpaceDepth < scene.cascadeSplits[i]) {
            layer = i;
            break;
        }
    }
    if (layer == -1) {
        // Occlude light on the back side of the body if out of shadow range.
        return simpleShadow(bodyPos, sunDirection);
    }

    // Transform to light space using the selected cascade matrix
    vec3 cascadePos = vec3(dvec3(globePos) - scene.lightSpaceOrigins[layer].xyz);
    vec4 fragPosLightSpace = scene.lightSpaceMatrices[layer] * vec4(cascadePos, 1.0);

    // Perspective divide and map to [0, 1] range
    vec3 projCoords = fragPosLightSpace.xyz / fragPosLightSpace.w;
    projCoords.xy = projCoords.xy * 0.5 + 0.5;

    // Handle boundaries
    if (projCoords.z > 1.0 || projCoords.z < 0.0 ||
        projCoords.x < 0.0 || projCoords.x > 1.0 ||
        projCoords.y < 0.0 || projCoords.y > 1.0) {
        return 0.0; // Outside shadow map bounds = unshadowed
    }

    float worldToNDCZ = length(vec3(
        scene.lightSpaceMatrices[layer][0][2],
        scene.lightSpaceMatrices[layer][1][2],
        scene.lightSpaceMatrices[layer][2][2]
    ));
    
    // Use the normal of the actual displaced triangle
    vec3 geometricNormal = cross(dFdx(cascadePos), dFdy(cascadePos));
    float geometricNormalLength = length(geometricNormal);
    geometricNormal = geometricNormalLength > 1e-6
        ? geometricNormal / geometricNormalLength
        : normalize(vs_out.normal);
    if (dot(geometricNormal, vs_out.normal) < 0.0) geometricNormal = -geometricNormal;

    float normalLightCos = clamp(
        dot(geometricNormal, normalize(scene.lightDirection)),
        0.0,
        1.0
    );
    float receiverSlope = sqrt(max(0.0, 1.0 - normalLightCos * normalLightCos))
                        / max(normalLightCos, 0.2);

    float precisionBiasWorld = 2.0 * length(globePos) * floatEpsilon;
    float receiverBiasWorld = max(0.5, precisionBiasWorld) + min(2.0, 0.5 * receiverSlope);
    float bias = receiverBiasWorld * worldToNDCZ;

    // PCF (Percentage-Closer Filtering) for soft edges
    float shadow = 0.0;
    vec2 texelSize = 1.0 / vec2(textureSize(shadowMapArray, 0));

    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            float pcfDepth = texture(shadowMapArray, vec3(projCoords.xy + vec2(x, y) * texelSize, layer)).r;
            shadow += (projCoords.z - bias > pcfDepth) ? 1.0 : 0.0;
        }
    }
    shadow /= 9.0;

    return shadow;
}

float castShadow() {
    return castShadow(vec3(0.0), GLOBE_RADIUS);
}
