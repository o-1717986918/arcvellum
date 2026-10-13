import { createHash } from "node:crypto";

/** Lifetime is one Agent context. A later invocation always starts with full content. */
export class ActiveContextReads {
    private readonly delivered = new Map<string, string>();
    receipt(value: Record<string, unknown>, toolCallId: string): Record<string, unknown> {
        const field = value.content !== undefined ? "content" : typeof value.text === "string" ? "text" : null;
        if (!field) return value;
        const digest = createHash("sha256").update(JSON.stringify(value, (_key, item) => {
            if (!item || typeof item !== "object" || Array.isArray(item)) return item;
            return Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]]));
        })).digest("hex");
        const prior = this.delivered.get(digest);
        if (!prior) { this.delivered.set(digest, toolCallId); return value; }
        const result = { ...value };
        delete result[field];
        return { ...result, content_receipt: { source_tool_call_id: prior, content_sha256: digest,
            availability: "already-in-this-agent-context" } };
    }
}
