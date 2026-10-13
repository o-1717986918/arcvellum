/** Reversible projection; original files and all literary source bytes remain intact. */
export function projectMaterialRead(value: Record<string, unknown>): Record<string, unknown> {
    if (!value.content || typeof value.content !== "object" || Array.isArray(value.content)) return value;
    const content = { ...value.content as Record<string, unknown> };
    for (const key of ["candidate_id", "kind", "target", "purpose", "scene_moment"]) {
        if (key in value && content[key] === value[key]) delete content[key];
    }
    const source = content.text;
    const spans: Record<string, unknown> = {};
    if (typeof source === "string" && !("source_field_spans" in content)) {
        for (const key of ["spoken", "first_person_action", "private_impulse"]) {
            const text = content[key];
            if (typeof text !== "string" || !text) continue;
            const start = source.indexOf(text);
            if (start < 0 || source.indexOf(text, start + 1) >= 0) continue;
            const span = { start, end: start + text.length, offset_unit: "utf16" };
            // A locator must not increase the serialized field size.
            const before = { ...content, ...(Object.keys(spans).length ? { source_field_spans: spans } : {}) };
            const after: Record<string, unknown> = { ...content, source_field_spans: { ...spans, [key]: span } };
            delete after[key];
            if (JSON.stringify(after).length >= JSON.stringify(before).length) continue;
            spans[key] = span;
            delete content[key];
        }
    }
    if (Object.keys(spans).length) content.source_field_spans = spans;
    return { ...value, content };
}
