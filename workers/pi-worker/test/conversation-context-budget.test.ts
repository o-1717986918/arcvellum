import { describe, expect, it } from "vitest";
import { replayInputEstimate } from "../src/conversation-context-budget.ts";

const budget = {maxInputTokens: 10000, systemPrompt: "系统指令", tools: []};
describe("conversation token estimates", () => {
  it("uses actual model usage for Chinese history instead of its UTF-8 size", () => {
    const messages: any[] = [{role:"assistant",content:[{type:"text",text:"月".repeat(4000)}],
      usage:{input:100,cacheRead:1000,cacheWrite:0,output:4000,totalTokens:5100}}];
    const result = replayInputEstimate(messages,"继续",budget);
    expect(Buffer.byteLength(JSON.stringify(messages),"utf8")).toBeGreaterThan(12000);
    expect(result.tokens).toBeGreaterThan(5100);
    expect(result.tokens).toBeLessThan(5300);
    expect(result.source).toBe("provider-usage-plus-upper-bound");
  });
  it("accounts for system instructions and tool schemas when usage is unavailable", () => {
    const small = replayInputEstimate([],"x",budget);
    const large = replayInputEstimate([],"x",{...budget,systemPrompt:"字".repeat(1000),tools:[{description:"x".repeat(300)}]});
    expect(large.tokens-small.tokens).toBeGreaterThan(3200);
    expect(large.source).toBe("byte-upper-bound");
  });
  it("includes tool results after the last reported response and never adds reasoning twice", () => {
    const messages: any[] = [{role:"assistant",usage:{input:100,cacheRead:800,output:100,
      reasoning:80,totalTokens:1000}},{role:"toolResult",content:[{type:"text",text:"工具结果".repeat(100)}]}];
    const result = replayInputEstimate(messages,"next",budget);
    expect(result.tokens).toBeGreaterThan(2200);
    expect(result.tokens).toBeLessThan(2400);
  });
});
