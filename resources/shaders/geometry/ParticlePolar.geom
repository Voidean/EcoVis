#version 430 core

layout(lines) in;
layout(line_strip, max_vertices = 2) out;

in vec2 vGlobalPos[];

#include "common/CoordinateConversion"

vec4 calcLocalPos(vec2 globalPos, bool isNorth) {
    vec2 uv = geoPosToPolarUV(uvToGeoPos(globalPos), isNorth);
    // uv = 1.0 - uv;
    return vec4(uv * 2.0 - 1.0, 0.0, 1.0);
}

void main() {
    vec2 p0 = vGlobalPos[0];
    vec2 p1 = vGlobalPos[1];

    bool isNorth = (p0.y > 0.5);
    gl_Layer = isNorth ? 0 : 1;

    gl_Position = calcLocalPos(p0, isNorth); EmitVertex();
    gl_Position = calcLocalPos(p1, isNorth); EmitVertex();
    EndPrimitive();
}
