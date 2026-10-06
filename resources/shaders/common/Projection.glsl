#include "common/CoordinateConstants"
#include "common/CoordinateConversion"

// Robinson table values
const float R_X[] = float[](1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600,
                            0.9427, 0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597,
                            0.7186, 0.6732, 0.6213, 0.5722, 0.5322);
const float R_Y[] = float[](0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720,
                            0.4340, 0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903,
                            0.8435, 0.8936, 0.9394, 0.9761, 1.0000);

float unscaleElevation(float elevation) {
    return elevation * (MAX_ELEVATION - MIN_ELEVATION) + MIN_ELEVATION;
}

vec3 projectToGlobe(vec3 geoPos) {
    float lon  = geoPos.x;
    float lat  = geoPos.y;
    float elev = geoPos.z;

    float x = cos(lat) * sin(lon);
    float y = -cos(lat) * cos(lon);
    float z = sin(lat);
    float r = GLOBE_RADIUS + elev * scene.verticalScale;

    return vec3(x, y, z) * r;
}

vec3 projectToEquiretangular(vec3 geoPos) {
    float lon  = geoPos.x;
    float lat  = geoPos.y;
    float elev = geoPos.z;

    float x = lon * GLOBE_RADIUS;
    float y = lat * GLOBE_RADIUS;
    float z = elev * scene.verticalScale;

    return vec3(x, y, z);
}

vec3 projectToMercator(vec3 geoPos) {
    float lon = geoPos.x;
    float lat = clamp(geoPos.y, -1.4844, 1.4844); // avoid infinity
    float elev = geoPos.z;

    float x = lon * GLOBE_RADIUS;

    float y = log(tan(PI / 4.0 + lat / 2.0));
    y = clamp(y, -3.0, 3.0) / 3.0 * PI * GLOBE_RADIUS;

    float z = elev * scene.verticalScale;

    return vec3(x, y, z);
}

vec3 projectToRobinson(vec3 geoPos) {
    float lon  = geoPos.x;
    float lat  = geoPos.y;
    float elev = geoPos.z;

    // Convert latitude to degrees and get absolute value for table lookup
    float absLatDeg = abs(lat) * 180.0 / PI;

    // Determine the index for the lookup table (0 to 18)
    float fIndex = clamp(absLatDeg / 5.0, 0.0, 18.0);
    int i = int(floor(fIndex));
    int j = int(ceil(fIndex));
    float t = fract(fIndex);

    // Interpolate values from the table
    float xFactor = mix(R_X[i], R_X[j], t);
    float yFactor = mix(R_Y[i], R_Y[j], t);

    // Apply sign back to latitude
    float ySign = sign(lat);

    // Calculate final coordinates
    // Multiply lon by x_factor, and normalize to -1.0 to 1.0 range
    float x = lon * xFactor * GLOBE_RADIUS;
    float y = ySign * 0.5 * yFactor * PI * GLOBE_RADIUS;
    float z = elev * scene.verticalScale;

    return vec3(x, y, z);
}

vec3 project(vec3 geoPos, int projectionMode) {
    if (projectionMode == 0) return projectToGlobe(geoPos);
    if (projectionMode == 1) return projectToEquiretangular(geoPos);
    if (projectionMode == 2) return projectToMercator(geoPos);
    if (projectionMode == 3) return projectToRobinson(geoPos);
    return vec3(0.0); // invalid projectionMode
}

vec3 unprojectFromGlobe(vec3 worldPos) {
    float r = length(worldPos);
    vec3 p = worldPos / r; // normalize

    float lon = atan(p.x, -p.y);
    float lat = asin(p.z);
    float elev = (r - GLOBE_RADIUS) / scene.verticalScale;

    return vec3(lon, lat, elev);
}

vec3 unprojectFromEquiretangular(vec3 worldPos) {
    float lon  = worldPos.x / GLOBE_RADIUS;
    float lat  = worldPos.y / GLOBE_RADIUS;
    float elev = worldPos.z / scene.verticalScale;
    return vec3(lon, lat, elev);
}

vec3 unprojectFromMercator(vec3 worldPos) {
    float lon = worldPos.x / GLOBE_RADIUS;

    float my = worldPos.y / (GLOBE_RADIUS * PI);
    float lat = 2.0 * (atan(exp(my * 3.0)) - (PI / 4.0));

    float elev = worldPos.z / scene.verticalScale;

    return vec3(lon, lat, elev);
}

vec3 unprojectFromRobinson(vec3 worldPos) {
    float mx   = worldPos.x / (GLOBE_RADIUS * PI);
    float my   = worldPos.y / (GLOBE_RADIUS * PI);

    // Clamp y_factor to avoid out-of-bounds due to precision issues
    float yFactor = clamp(abs(my) / 0.5, 0.0, 1.0);
    float ySign = sign(my);

    int idx = 0;
    // Iterate to find the correct interval (19 elements means max index is 18)
    for (int i = 0; i < 18; i++) {
        if (R_Y[i] <= yFactor && yFactor <= R_Y[i + 1]) {
            idx = i;
            break;
        }
    }

    float t = (yFactor - R_Y[idx]) / (R_Y[idx + 1] - R_Y[idx]);
    float xFactor = mix(R_X[idx], R_X[idx + 1], t);
    float lon = (mx * PI) / xFactor;

    float fIndex = float(idx) + t;
    float latDeg = fIndex * 5.0;
    float lat = radians(latDeg) * ySign;

    float elev = worldPos.z / scene.verticalScale;

    return vec3(lon, lat, elev);
}

vec3 unproject(vec3 worldPos, int projectionMode) {
    if (projectionMode == 0) return unprojectFromGlobe(worldPos);
    if (projectionMode == 1) return unprojectFromEquiretangular(worldPos);
    if (projectionMode == 2) return unprojectFromMercator(worldPos);
    if (projectionMode == 3) return unprojectFromRobinson(worldPos);
    return vec3(0.0); // invalid projectionMode
}
