#version 430 core
layout(location = 0, index = 0) out vec4 FragColor;
layout(location = 0, index = 1) out vec4 BlendTransmittance;

in vec2 TexCoords;

uniform sampler2D depthMap;
uniform sampler2DMS depthMapMS;
uniform int depthSamples;
uniform sampler2D sunLUT;
uniform sampler2D sky;
uniform mat3 skyRotation;

#include "common/SceneDataBuffer"
#include "common/Projection"

const float atmosphereRadius = 1.05 * GLOBE_RADIUS;
const float atmosphereThickness = atmosphereRadius - GLOBE_RADIUS;
const vec3 flatNormal = vec3(0.0, 0.0, 1.0);

const float hScale = 0.0075 * GLOBE_RADIUS;
const int samples = 10;
const float intensity = 5.0;

const vec3 betaRay = vec3(5.8e-6, 13.5e-6, 33.1e-6) / 25.0;
const vec3 betaExtinction = betaRay * vec3(0.8, 1.25, 1.5);

const float starFadeSensitivity = 15.0;

#include "common/Skybox"

vec3 safeNormalize(vec3 value, vec3 fallback) {
    float lengthSquared = dot(value, value);
    return lengthSquared > 1e-20 ? value * inversesqrt(lengthSquared) : fallback;
}

void writeComposite(vec3 sourceColor, vec3 transmittance) {
    FragColor = vec4(max(sourceColor, vec3(0.0)), 0.0);
    BlendTransmittance = vec4(clamp(transmittance, 0.0, 1.0), 1.0);
}

struct DepthInfo {
    float nearestDepth;
    float coverage;
};

DepthInfo readDepthInfo() {
    if (depthSamples > 1) {
        ivec2 pixel = ivec2(gl_FragCoord.xy);
        float nearestDepth = 0.0;
        float coveredSamples = 0.0;

        for (int sampleIndex = 0; sampleIndex < depthSamples; sampleIndex++) {
            float sampleDepth = texelFetch(depthMapMS, pixel, sampleIndex).r;
            if (sampleDepth > 0.0) {
                nearestDepth = max(nearestDepth, sampleDepth);
                coveredSamples += 1.0;
            }
        }
        return DepthInfo(nearestDepth, coveredSamples / float(depthSamples));
    }

    float depth = texelFetch(depthMap, ivec2(gl_FragCoord.xy), 0).r;
    bool covered = depth > 0.0;
    return DepthInfo(covered ? depth : 0.0, covered ? 1.0 : 0.0);
}

vec2 raySphereIntersect(vec3 r0, vec3 rd, float radius) {
    float b = dot(r0, rd);
    vec3 perp = r0 - b * rd;
    float h = radius * radius - dot(perp, perp);
    if (h < 0.0) return vec2(-1.0);
    h = sqrt(h);
    return vec2(-b - h, -b + h);
}

float getSunOpticalDepth(vec3 pos, float height) {
    float cosThetaSun = dot(safeNormalize(pos, vec3(0.0, 0.0, 1.0)), scene.lightDirection);
    float u = (cosThetaSun + 1.0) * 0.5;
    float v = clamp(height / atmosphereThickness, 0.0, 1.0);
    return texture(sunLUT, vec2(u, v)).r;
}

struct AtmosphereResult {
    vec3 scattering;
    float opticalDepth;
};

AtmosphereResult integrateAtmosphere(vec3 viewPos, vec3 rayDir, float tStart, float tEnd) {
    AtmosphereResult result = AtmosphereResult(vec3(0.0), 0.0);
    if (tEnd <= tStart) return result;

    float segmentLength = (tEnd - tStart) / float(samples);
    float tCurrent = tStart;
    vec3 totalScattering = vec3(0.0);
    float r2Min = GLOBE_RADIUS * GLOBE_RADIUS * 0.9025;
    float r2Max = GLOBE_RADIUS * GLOBE_RADIUS;

    for (int i = 0; i < samples; i++) {
        vec3 samplePos = viewPos + rayDir * (tCurrent + segmentLength * 0.5);
        float height = length(samplePos) - GLOBE_RADIUS;

        float localDensity = exp(-max(height, 0.0) / hScale) * segmentLength;
        result.opticalDepth += localDensity;

        vec3 sampleNormal = safeNormalize(samplePos, -rayDir);
        float shadowDepth = dot(sampleNormal, scene.lightDirection);

        float shadowMultiplier = 1.0;
        if (shadowDepth < 0.0) {
            vec3 shadowCross = cross(samplePos, scene.lightDirection);
            float shadowAxisDist2 = dot(shadowCross, shadowCross);
            shadowMultiplier = smoothstep(r2Min, r2Max, shadowAxisDist2);
        }

        if (shadowMultiplier > 0.0) {
            float totalOpticalDepth = result.opticalDepth + getSunOpticalDepth(samplePos, height);
            vec3 transmittance = exp(-betaExtinction * totalOpticalDepth);
            totalScattering += localDensity * transmittance * shadowMultiplier;
        }

        tCurrent += segmentLength;
    }

    float cosTheta = dot(rayDir, scene.lightDirection);
    float phase = 0.75 * (1.0 + cosTheta * cosTheta);
    result.scattering = totalScattering * betaRay * phase * intensity;
    return result;
}

void main() {
    DepthInfo depthInfo = readDepthInfo();
    float depth = depthInfo.nearestDepth;
    float sceneCoverage = depthInfo.coverage;
    bool hasScene = sceneCoverage > 0.0;

    vec4 clipPos = vec4(TexCoords * 2.0 - 1.0, depth, 1.0);
    vec4 worldPos = scene.invViewProj * clipPos;
    vec3 viewPos = scene.viewPos;
    vec3 cameraForward = safeNormalize(
        transpose(mat3(scene.view)) * vec3(0.0, 0.0, -1.0),
        vec3(0.0, 1.0, 0.0)
    );

    if (hasScene && abs(worldPos.w) <= 1e-20) {
        writeComposite(vec3(0.0), vec3(1.0));
        return;
    }

    vec3 sceneWorldPos = !hasScene
        ? (viewPos + safeNormalize(worldPos.xyz, cameraForward) * 1e10)
        : (worldPos.xyz / worldPos.w);

    vec3 rayDir = safeNormalize(sceneWorldPos - viewPos, cameraForward);
    float sceneDist = length(sceneWorldPos - viewPos);

    if (scene.projectionMode != 0) {
        if (hasScene) {
            sceneWorldPos = projectToGlobe(unproject(sceneWorldPos, scene.projectionMode));

            vec3 globeNormal = safeNormalize(sceneWorldPos, flatNormal);
            vec3 axis = cross(flatNormal, globeNormal);
            float cosA = dot(flatNormal, globeNormal);

            if (cosA < -0.9999) {
                rayDir = -rayDir;
            } else {
                rayDir = rayDir + cross(axis, rayDir) + cross(axis, cross(axis, rayDir)) * (1.0 / (1.0 + cosA));
            }
            rayDir = safeNormalize(rayDir, cameraForward);
            viewPos = sceneWorldPos - rayDir * sceneDist;
        } else {
            vec3 flatCamSurface = vec3(scene.viewPos.xy, 0.0);
            vec3 globeGeoPos = unproject(flatCamSurface, scene.projectionMode);

            if (abs(globeGeoPos.x) > PI || abs(globeGeoPos.y) > PI / 2.0) {
                writeComposite(vec3(0.0), vec3(1.0));
                return;
            }

            vec3 globeSurfacePos = projectToGlobe(globeGeoPos);
            vec3 globeNormal = safeNormalize(globeSurfacePos, flatNormal);

            vec3 axis = cross(flatNormal, globeNormal);
            float cosA = dot(flatNormal, globeNormal);

            if (cosA < -0.9999) {
                rayDir = -rayDir;
            } else {
                rayDir = rayDir + cross(axis, rayDir) + cross(axis, cross(axis, rayDir)) * (1.0 / (1.0 + cosA));
            }
            rayDir = safeNormalize(rayDir, cameraForward);
            viewPos = globeSurfacePos + globeNormal * scene.viewPos.z;
        }
    }

    vec3 skyColor = getSkyColor(rayDir);
    vec3 backgroundSource = skyColor;
    vec3 surfaceSource = vec3(0.0);
    vec3 surfaceTransmittance = vec3(1.0);

    float b = dot(viewPos, rayDir);
    vec3 perp = viewPos - b * rayDir;
    float discriminant = atmosphereRadius * atmosphereRadius - dot(perp, perp);
    float discriminantWidth = fwidth(discriminant);
    float atmosphereCoverage = smoothstep(-max(discriminantWidth, 1.0), max(discriminantWidth, 1.0), discriminant);

    vec2 tAtm = raySphereIntersect(viewPos, rayDir, atmosphereRadius);
    float tStart = max(tAtm.x, 0.0);
    float tEnd = max(tAtm.y, tStart);

    if (sceneCoverage < 1.0) {
        float sunPixelWidth = getSunPixelWidth(rayDir);
        vec3 clearSunColor = getSunColor(rayDir, vec3(1.0), sunPixelWidth);
        vec3 clearBackground = skyColor + clearSunColor;

        AtmosphereResult backgroundAtmosphere = integrateAtmosphere(viewPos, rayDir, tStart, tEnd);
        vec3 scatteredBackground = 1.0 - exp(-backgroundAtmosphere.scattering);
        float skyLuminance = dot(backgroundAtmosphere.scattering, vec3(0.2126, 0.7152, 0.0722));
        float daylightFade = exp(-skyLuminance * starFadeSensitivity);
        vec3 sunTransmittance = exp(-betaExtinction * backgroundAtmosphere.opticalDepth * 5.0);

        vec3 atmosphereBackground = scatteredBackground
            + skyColor * daylightFade
            + getSunColor(rayDir, sunTransmittance, sunPixelWidth);
        backgroundSource = mix(clearBackground, atmosphereBackground, atmosphereCoverage);
    }

    if (hasScene) {
        float surfaceEnd = min(tEnd, sceneDist);
        AtmosphereResult surfaceAtmosphere = integrateAtmosphere(viewPos, rayDir, tStart, surfaceEnd);
        vec3 scatteredSurface = 1.0 - exp(-surfaceAtmosphere.scattering);
        vec3 transmittedSurface = exp(-betaExtinction * surfaceAtmosphere.opticalDepth);

        surfaceSource = scatteredSurface * atmosphereCoverage;
        surfaceTransmittance = mix(vec3(1.0), transmittedSurface, atmosphereCoverage);
    }

    vec3 finalColor = surfaceSource * sceneCoverage + backgroundSource * (1.0 - sceneCoverage);
    writeComposite(finalColor, surfaceTransmittance);
}
