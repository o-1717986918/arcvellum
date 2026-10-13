import { describe, expect, it } from "vitest";
import { cacheUsageObservation, observeCacheStream, RequestShapeObserver } from "../src/cache-observation.ts";

describe("raw cache observation", () => {
  it("distinguishes absent, explicit zero, hits and contradictory fields", () => {
    expect(cacheUsageObservation({ prompt_tokens: 100 }).status).toBe("not-reported");
    expect(cacheUsageObservation({ prompt_tokens_details: { cached_tokens: 0 } }).status).toBe("reported");
    expect(cacheUsageObservation({ prompt_tokens: 100, prompt_cache_hit_tokens: 80, prompt_cache_miss_tokens: 20 }).cache_read_tokens).toBe(80);
    expect(cacheUsageObservation({ prompt_tokens_details: { cached_tokens: 0 }, prompt_cache_hit_tokens: 80 }).status).toBe("inconsistent");
    expect(cacheUsageObservation({ prompt_tokens: 10, prompt_cache_hit_tokens: 20 }).status).toBe("inconsistent");
  });
  it("preserves split UTF-8 bytes and excludes generated text from observations", async () => {
    const bytes = new TextEncoder().encode('data: {"choices":[{"delta":{"content":"秘密汉字"}}]}\n\ndata: {"usage":{"prompt_tokens":90,"prompt_tokens_details":{"cached_tokens":60}}}\n\ndata: [DONE]\n\n');
    const source = new ReadableStream<Uint8Array>({ start(c) { for (let i=0;i<bytes.length;i+=7) c.enqueue(bytes.slice(i,i+7)); c.close(); } });
    const events: unknown[] = [];
    const tapped = observeCacheStream(new Response(source,{headers:{"content-type":"text/event-stream"}}),
      (event,data)=>events.push({event,data}),{model_request_id:"r"});
    expect(new Uint8Array(await tapped.arrayBuffer())).toEqual(bytes);
    expect(events).toHaveLength(1);
    expect(JSON.stringify(events)).not.toContain("秘密");
    expect(JSON.stringify(events)).toContain('"cache_read_tokens":60');
  });
  it("a huge or malformed event cannot corrupt later valid usage", async () => {
    const body = "data: " + "x".repeat(70_000) + '\n' + 'data: {"usage":{"prompt_cache_hit_tokens":0}}\n';
    const events: any[]=[];
    expect(await observeCacheStream(new Response(body,{headers:{"content-type":"text/event-stream"}}),
      (event,data)=>events.push({event,data}),{}).text()).toBe(body);
    expect(events).toHaveLength(1);
  });
  it("request observations retain hashes and lengths rather than payload text", () => {
    const events: any[]=[]; const observer=new RequestShapeObserver((event,data)=>events.push(data),()=>({}));
    observer.observe({messages:[{role:"system",content:"private"}],tools:[]});
    observer.observe({messages:[{role:"system",content:"private"},{role:"user",content:"next"}],tools:[]});
    expect(events[1].common_prefix_bytes).toBeGreaterThan(0);
    expect(events[0].common_prefix_bytes).toBeNull();
    expect(JSON.stringify(events)).not.toMatch(/private|next/);
  });
});
