#version 430 core

out vec4 FragColor;

uniform vec4 pointColor = vec4(1.0);

void main() {
    float radius = length(gl_PointCoord - vec2(0.5));
    if (radius > 0.5) discard;

    float interior = 1.0 - smoothstep(0.36, 0.50, radius);
    vec3 outlineColor = vec3(0.03);
    FragColor = vec4(mix(outlineColor, pointColor.rgb, interior), pointColor.a);
}
