vec3 normalMap() {
    mat3 TBN = mat3(normalize(vs_out.tangent), normalize(vs_out.bitangent), normalize(vs_out.normal));
    vec3 normalTS = texture(material.normalMap, vs_out.texCoord).rgb;
    normalTS = normalize(normalTS * 2.0 - 1.0);
    return normalize(TBN * normalTS);
}

vec3 normalMap(vec2 texCoord) {
    mat3 TBN = mat3(normalize(vs_out.tangent), normalize(vs_out.bitangent), normalize(vs_out.normal));
    vec3 normalTS = texture(material.normalMap, texCoord).rgb;
    normalTS = normalize(normalTS * 2.0 - 1.0);
    return normalize(TBN * normalTS);
}
