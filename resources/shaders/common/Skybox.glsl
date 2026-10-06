const float sunAngularRadius = 0.025;
const vec3 sunBaseColor = vec3(1.0, 0.94, 0.78);

float sunHash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float sunNoise(vec2 p) {
    vec2 cell = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    return mix(
        mix(sunHash(cell), sunHash(cell + vec2(1.0, 0.0)), f.x),
        mix(sunHash(cell + vec2(0.0, 1.0)), sunHash(cell + vec2(1.0)), f.x),
        f.y
    );
}

float getSunPixelWidth(vec3 rayDir) {
    if (scene.projectionMode != 0) return 1e-5;
    vec3 sunDir = normalize(scene.lightDirection);
    float sunDistance = length(rayDir - sunDir);
    return max(fwidth(sunDistance), 1e-5);
}

vec3 getSunColor(vec3 rayDir, vec3 atmosphericTransmittance, float pixelWidth) {
    if (scene.projectionMode != 0) return vec3(0.0);

    vec3 sunDir = normalize(scene.lightDirection);
    float sunDistance = length(rayDir - sunDir);

    // Early exit if outside glare/corona threshold
    if (sunDistance > 0.25) return vec3(0.0);

    mat3 cameraRotation = transpose(mat3(scene.view));
    vec3 cameraRight = normalize(cameraRotation * vec3(1.0, 0.0, 0.0));
    vec3 cameraForward = normalize(cameraRotation * vec3(0.0, 0.0, -1.0));

    vec3 projectedRight = cameraRight - sunDir * dot(cameraRight, sunDir);
    vec3 fallbackAxis = abs(sunDir.z) < 0.95 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec3 tangent = length(projectedRight) > 1e-4
        ? normalize(projectedRight)
        : normalize(cross(fallbackAxis, sunDir));
    vec3 bitangent = cross(sunDir, tangent);
    vec2 solarUv = vec2(dot(rayDir, tangent), dot(rayDir, bitangent)) / sunAngularRadius;
    float solarAngle = atan(solarUv.y, solarUv.x);

    float viewAlignment = clamp(dot(cameraForward, sunDir), 0.0, 1.0);
    float offAxis = sqrt(max(1.0 - viewAlignment * viewAlignment, 0.0));
    float edgeInfluence = smoothstep(0.08, 0.55, offAxis);

    float edgeNoise = sin(solarAngle * 5.0 + 0.8) * 0.28;
    edgeNoise += sin(solarAngle * 9.0 - 1.3) * 0.14;
    edgeNoise += sin(solarAngle * 17.0 + 2.4) * 0.08;
    float localRadius = sunAngularRadius * (1.0 + edgeNoise * 0.02);
    float disc = 1.0 - smoothstep(localRadius - pixelWidth, localRadius + pixelWidth, sunDistance);

    // Skip procedural noise outside solar disc
    float photosphere = 1.0;
    if (disc > 0.0) {
        float radius = length(solarUv);
        float limb = sqrt(clamp(1.0 - radius * radius, 0.0, 1.0));
        float granulation = sunNoise(solarUv * 24.0) * 0.65 + sunNoise(solarUv * 57.0 + 8.3) * 0.35;
        photosphere = mix(0.58, 1.15, limb) * mix(0.88, 1.12, granulation);
    }

    float outsideDisc = max(sunDistance - sunAngularRadius, 0.0) * 2.0;
    float halo = exp(-outsideDisc * 42.0) * (1.0 - disc);

    float frontalRays = pow(0.5 + 0.5 * sin(solarAngle * 17.0 * offAxis + sin(solarAngle * 3.0) * 2.4), 10.0);
    frontalRays += 0.5 * pow(0.5 + 0.5 * sin(solarAngle * 13.0 * offAxis - 1.7), 18.0);

    float obliqueRays = pow(0.5 + 0.5 * sin(solarAngle * 7.0 - 0.9), 16.0);
    obliqueRays += 0.4 * pow(0.5 + 0.5 * sin(solarAngle * 3.0 + 1.4), 28.0);
    float rayPattern = mix(frontalRays, obliqueRays, edgeInfluence);

    vec2 sunViewOffset = vec2(dot(cameraForward, tangent), dot(cameraForward, bitangent));
    vec2 sunViewAxis = length(sunViewOffset) > 1e-4 ? normalize(sunViewOffset) : vec2(1.0, 0.0);
    vec2 coronaDirection = length(solarUv) > 1e-4 ? normalize(solarUv) : sunViewAxis;
    float lensStreak = pow(abs(dot(coronaDirection, sunViewAxis)), 20.0) * edgeInfluence;
    float coronaFalloff = mix(18.0, 7.0, lensStreak);
    float corona = (rayPattern + lensStreak * 0.65) * exp(-outsideDisc * coronaFalloff) * (1.0 - disc);
    float glare = 0.0015 / (sunDistance * sunDistance + 0.0015);

    vec3 transmittedSun = sunBaseColor * atmosphericTransmittance;
    float transmissionPeak = max(max(transmittedSun.r, transmittedSun.g), transmittedSun.b);
    vec3 sunsetColor = transmittedSun / max(transmissionPeak, 1e-4);
    float sunBrightness = mix(transmissionPeak, sqrt(transmissionPeak), 0.55);

    vec3 discColor = sunsetColor * photosphere * disc * (2.8 * sunBrightness);
    vec3 glowColor = sunsetColor * (halo * 0.4 + corona * 0.1 + glare * 0.1) * sunBrightness;
    return discColor + glowColor;
}

vec3 getSunColor(vec3 rayDir, vec3 atmosphericTransmittance) {
    return getSunColor(rayDir, atmosphericTransmittance, getSunPixelWidth(rayDir));
}

vec3 getSkyColor(vec3 dir) {
    if (scene.projectionMode != 0) return vec3(0.0);

    dir = normalize(skyRotation * dir);

    float u = atan(-dir.x, -dir.y) / (2.0 * PI) + 0.5;
    float v = asin(clamp(dir.z, -1.0, 1.0)) / PI + 0.5;

    vec2 uv = vec2(u, v);

    vec2 dx = dFdx(uv);
    vec2 dy = dFdy(uv);

    // Wrap the U derivative into [-0.5, 0.5]
    dx.x -= round(dx.x);
    dy.x -= round(dy.x);

    return textureGrad(sky, uv, dx, dy).rgb;
}
