#define BINDING 0
#define IDENTIFIER drawCmd

struct DrawElementsIndirectCommand {
    uint count;
    uint instanceCount;
    uint firstIndex;
    uint baseVertex;
    uint baseInstance;
};

layout(std430, binding = BINDING) buffer DrawCommandBuffer {
    DrawElementsIndirectCommand IDENTIFIER;
};
