#version 430 core
in float vDist;

out vec4 FragColor;

uniform vec4 lineColor = vec4(1.0, 1.0, 1.0, 1.0);

uniform bool dashed;
uniform float dashSize;
uniform float gapSize;

void main() {
    if (dashed && mod(vDist, dashSize + gapSize) > dashSize) discard;
    FragColor = lineColor;
}