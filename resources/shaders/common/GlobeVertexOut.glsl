#define dir out

dir VS_OUT {
    vec3 worldPos;

    vec4 vertexColor;
    vec2 texCoord;
    vec3 normal;

    vec3 layerTexCoord;
    vec3 geoPos;
    flat ivec3 nodePos;
} vs_out;
