import type { AgentMessage } from "@earendil-works/pi-agent-core";

export interface ReplayContextBudget {
  maxInputTokens: number;
  systemPrompt: string;
  tools: unknown[];
}

const record = (value: unknown): value is Record<string, any> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown): number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : 0;
// No tokenizer is exposed by this SDK. UTF-8 bytes provide a conservative BPE
// upper bound only for unseen content; reported model usage anchors restored context.
const upperBound = (value: unknown): number =>
  Buffer.byteLength(JSON.stringify(value) ?? "", "utf8") + 32;

export function replayInputEstimate(messages: AgentMessage[], prompt: string, budget: ReplayContextBudget) {
  for (let index = messages.length - 1; index >= 0; index--) {
    const message: unknown = messages[index];
    if (!record(message) || message.role !== "assistant" || !record(message.usage)) continue;
    const usage = message.usage;
    const reported = Math.max(count(usage.totalTokens),
      count(usage.input) + count(usage.cacheRead) + count(usage.cacheWrite) + count(usage.output));
    if (!reported) continue;
    return {
      tokens: reported + upperBound(messages.slice(index + 1)) + upperBound(prompt),
      source: "provider-usage-plus-upper-bound",
    };
  }
  return {
    tokens: upperBound({ systemPrompt: budget.systemPrompt, tools: budget.tools, messages }) + upperBound(prompt),
    source: "byte-upper-bound",
  };
}
