uniform int cullFrustumPlaneCount;
uniform vec4 cullFrustumPlanes[6];
uniform vec3 cullViewPos;

bool frustumCulling(vec3 pos, float radius) {
    for (int i = 0; i < cullFrustumPlaneCount; i++) {
        float dist = dot(cullFrustumPlanes[i].xyz, pos) + cullFrustumPlanes[i].w;
        // If the bounding sphere is entirely behind ANY plane, cull it
        if (dist < -radius) return true;
    }
    return false;
}


bool occlusionCulling(vec3 pos, float radius) {
    if (scene.projectionMode == 0) {
        float r = GLOBE_RADIUS + radius;
        float r_sq = r * r;

        vec3 camPos = cullViewPos;
        float c_sq = dot(camPos, camPos);

        // Only process occlusion if camera is outside the globe's bounding volume
        if (c_sq > r_sq) {
            vec3 v = pos - camPos;

            // Check if the vector to the tile is pointing towards the globe (-camPos)
            float lhs = dot(-camPos, v);

            // If lhs > 0, the tile is physically behind the horizon plane
            if (lhs > 0.0) {
                lhs *= lhs;
                float rhs = (1.0 - r_sq / c_sq) * c_sq * dot(v, v);

                // If it falls within the globe's occluding cone, cull it
                if (lhs < rhs) return true;
            }
        }
    }
    return false;
}
