#version 430 core

layout(lines) in;
layout(line_strip, max_vertices = 4) out;

in int vLayer[];
in vec2 vGlobalPos[];
in vec2 vTileMin[];
in vec2 vTileMax[];

vec4 calcLocalPos(vec2 globalPos, vec2 tileMin, vec2 tileMax) {
    vec2 uv = (globalPos - tileMin) / (tileMax - tileMin);
    uv.y = 1.0 - uv.y;
    return vec4(uv * 2.0 - 1.0, 0.0, 1.0);
}

void main() {
    int startLayer = vLayer[0];
    int endLayer = vLayer[1];

    if (startLayer == -1 || endLayer == -1) return;

    vec2 p0 = vGlobalPos[0];
    vec2 p1 = vGlobalPos[1];

    vec2 p1_start = p1;
    if (p1.x - p0.x > 0.5) p1_start.x -= 1.0;
    else if (p0.x - p1.x > 0.5) p1_start.x += 1.0;

    gl_Layer = startLayer;
    gl_Position = calcLocalPos(p0, vTileMin[0], vTileMax[0]); EmitVertex();
    gl_Position = calcLocalPos(p1_start, vTileMin[0], vTileMax[0]); EmitVertex();
    EndPrimitive();

    bool wrapped = abs(p1.x - p0.x) > 0.5;

    if (startLayer != endLayer || wrapped) {
        vec2 p0_end = p0;
        if (p0.x - p1.x > 0.5) p0_end.x -= 1.0;
        else if (p1.x - p0.x > 0.5) p0_end.x += 1.0;

        gl_Layer = endLayer;
        gl_Position = calcLocalPos(p0_end, vTileMin[1], vTileMax[1]); EmitVertex();
        gl_Position = calcLocalPos(p1, vTileMin[1], vTileMax[1]); EmitVertex();
        EndPrimitive();
    }
}