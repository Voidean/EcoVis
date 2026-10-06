#define BINDING 0

struct Particle {
    vec2 pos;
    float life;
    float seed;

    vec2 lastPos;
    float padding2;
    float padding3;
};

layout(std430, binding = BINDING) buffer ParticleBuffer {
    Particle particles[];
};