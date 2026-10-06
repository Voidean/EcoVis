#define BINDING 0

layout (std430, binding = BINDING) buffer MapTileBuffer {
    ivec4 nodePosLayer[]; // .xyz = column, row, level. .w = texture layer index
};
