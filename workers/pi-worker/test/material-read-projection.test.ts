import { describe, expect, it } from "vitest";
import { projectMaterialRead } from "../src/material-read-projection.ts";

describe("lossless material source projection", () => {
    it("keeps the full long source, reconstructs unique fields and preserves unequal metadata", () => {
        const spoken = "我还记得那个月亮。" .repeat(20);
        const text = "🐟" + spoken + "我走过许多街巷。" .repeat(1000);
        const original = { candidate_id: "a", kind: "actor", target: "阿青", content: {
            candidate_id: "a", kind: "actor", target: "另一版本", text, spoken, private_impulse: "短念头" } };
        const projected = projectMaterialRead(original);
        const content = projected.content as Record<string, any>;
        const span = content.source_field_spans.spoken;
        expect(content.text).toBe(text);
        expect(content.text.slice(span.start, span.end)).toBe(spoken);
        expect(span.offset_unit).toBe("utf16");
        expect(content.target).toBe("另一版本");
        expect(content.private_impulse).toBe("短念头");
        expect(content.candidate_id).toBeUndefined();
        expect(JSON.stringify(projected).length).toBeLessThan(JSON.stringify(original).length);
        expect(original.content.spoken).toBe(spoken);
        expect(projectMaterialRead(projected)).toEqual(projected);
    });
    it("retains ambiguous and absent source fields verbatim", () => {
        const spoken = "重复语句".repeat(40);
        const original = { content: { text: spoken + "中间" + spoken, spoken,
            first_person_action: "没有出现在原文中的动作".repeat(20) } };
        expect(projectMaterialRead(original)).toEqual(original);
    });
});
