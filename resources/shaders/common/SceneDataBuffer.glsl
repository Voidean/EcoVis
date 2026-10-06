#define BINDING 0

const int MAX_SHADOW_CASCADES = 10;

layout (std140, binding = BINDING) uniform SceneData {
    mat4 view;
    mat4 projection;
    mat4 viewProjection;
    mat4 viewNoTrans;
    mat4 viewProjNoTrans;
    mat4 invViewProj;

    dvec3 dViewPos;
    vec3 viewPos;

    int projectionMode;
    float verticalScale;

    bool enableShadows;
    vec3 lightDirection;
    float ambient;

    vec4 frustumPlanes[5];

    mat4 lightSpaceMatrices[MAX_SHADOW_CASCADES];
    dvec4 lightSpaceOrigins[MAX_SHADOW_CASCADES];
    float cascadeSplits[MAX_SHADOW_CASCADES];
    int cascadeCount;
} scene;
