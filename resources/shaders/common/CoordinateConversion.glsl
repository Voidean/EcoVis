#include "common/CoordinateConstants"

vec2 quadTreeNodeToGeoPos(ivec3 nodePos, vec2 uv) {
    float column = float(nodePos.x);
    float row    = float(nodePos.y);
    int level  = nodePos.z;

    uv.y = 1.0 - uv.y;

    float n = exp2(level);

    float x = (column + uv.x) / n;
    float y = (row + uv.y) / n;

    float longitude = ((x * 2.0) - 1.0) * PI;
    float latitude  = atan(sinh((1.0 - (y * 2.0)) * PI));

    return vec2(longitude, latitude);
}

vec2 geoPosToUv(vec2 geoPos) {
    float u = (geoPos.x / PI + 1.0) / 2.0;
    float v = geoPos.y / PI + 0.5;
    return vec2(u, v);
}

vec2 uvToGeoPos(vec2 uv) {
    float lon = ((uv.x * 2.0) - 1.0) * PI;
    float lat = (uv.y - 0.5) * PI;
    return vec2(lon, lat);
}

vec2 equiretangularUvToMercatorUv(vec2 equiPos) {
    float lat = (equiPos.y - 0.5) * PI;
    lat = clamp(lat, -MAX_MERCATOR_LAT, MAX_MERCATOR_LAT);
    float mercM = log(tan(0.25 * PI + 0.5 * lat));
    float mercY = 0.5 - (mercM / (2.0 * PI));

    return vec2(equiPos.x, mercY);
}

const float MAX_POLAR_LATITUDE = radians(10.0);

vec2 geoPosToPolarUV(vec2 geoPos, bool isNorth) {
    float lon = geoPos.x;
    float lat = geoPos.y;

    float d = isNorth ? (PI * 0.5 - lat) : (lat + PI * 0.5);
    float r = d / MAX_POLAR_LATITUDE;

    return vec2(0.5 + 0.5 * r * sin(lon), 0.5 + 0.5 * r * cos(lon));
}
