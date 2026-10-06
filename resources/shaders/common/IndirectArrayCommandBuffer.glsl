#define BINDING 0
#define IDENTIFIER drawCmd

struct DrawArraysIndirectCommand {
    uint count;         // Number of vertices to draw (indices * 2 for lines)
    uint instanceCount; // 1
    uint first;         // 0
    uint baseInstance;  // 0 (padding)
};

layout(std430, binding = BINDING) buffer DrawCommandBuffer {
    DrawArraysIndirectCommand IDENTIFIER;
};
