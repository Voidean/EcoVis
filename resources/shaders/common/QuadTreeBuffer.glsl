#define BINDING 0

struct QuadTreeNode {
    int children[4]; // Indices of children. -1 if it's a leaf.

    int layerIndex;  // The layer index for TextureArrays. -1 if not loaded.
    int padding[3];
};

layout(std430, binding = BINDING) buffer QuadTreeBuffer {
    QuadTreeNode treeNodes[];
};