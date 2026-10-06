#version 430 core

const int MAX_LOD = 16;

out int vLayer;
out vec2 vGlobalPos;
out vec2 vTileMin;
out vec2 vTileMax;

#include "common/ParticleBuffer" (BINDING=0)
#include "common/QuadTreeBuffer" (BINDING=1)
#include "common/CoordinateConversion"

void main() {
    uint particleIdx = gl_VertexID / 2;
    bool isEndPoint = (gl_VertexID % 2 == 1);

    Particle p = particles[particleIdx];
    vec2 equiPos = isEndPoint ? p.pos : p.lastPos;
    vec2 targetPos = equiretangularUvToMercatorUv(equiPos);

    // Calculate Texture Layer
    int currentNode = 0; // Start at root
    vec2 currentMin = vec2(0.0);
    vec2 currentMax = vec2(1.0);

    for (int i = 0; i <= MAX_LOD; i++) {
        if (treeNodes[currentNode].children[0] == -1) break; // Exit if it's a leaf

        // Calculate the midpoint of the current QuadTree node
        vec2 mid = (currentMin + currentMax) * 0.5;

        // Determine which of the 4 children the particle's UV falls into
        // 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight
        int childOffset = 0;
        if (targetPos.x >= mid.x) { childOffset += 1; currentMin.x = mid.x; } else { currentMax.x = mid.x; }
        if (targetPos.y >= mid.y) { childOffset += 2; currentMin.y = mid.y; } else { currentMax.y = mid.y; }

        currentNode = treeNodes[currentNode].children[childOffset];
    }

    vLayer = treeNodes[currentNode].layerIndex;
    vGlobalPos = targetPos;
    vTileMin = currentMin;
    vTileMax = currentMax;
}