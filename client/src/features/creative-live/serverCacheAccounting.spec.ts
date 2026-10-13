import { describe, expect, it } from "vitest";
import { addServerCache } from "./serverCacheAccounting";
import { reduceAccounting } from "./usageAccounting";
import type { CreativeLiveSnapshot, CreativeLiveEvent } from "./types";
describe("server cache reporting",()=>{
  it("captures raw fields without counting them as a second usage update during streaming",()=>{
    const snapshot={usage:{total_tokens:0,cost_usd:0,updates:0},events:[]} as unknown as CreativeLiveSnapshot;
    const raw={event:"runner.cache.usage.observed",channel:"usage",event_id:"raw",
      data:{model_request_id:"a",status:"reported",prompt_tokens:100,cache_read_tokens:0}} as unknown as CreativeLiveEvent;
    snapshot.usage_accounting=reduceAccounting(snapshot,raw);
    expect(snapshot.usage_accounting.updates).toBe(0);
    const usage={event:"usage.updated",channel:"usage",event_id:"usage",data:{model_request_id:"a",
      usage_id:"arcvellum-conversation-a",usage:{input:100,output:10,total_tokens:110}}} as unknown as CreativeLiveEvent;
    snapshot.usage_accounting=reduceAccounting(snapshot,usage);
    snapshot.usage_accounting=reduceAccounting(snapshot,usage);
    expect(snapshot.usage_accounting.updates).toBe(1);
    expect(snapshot.usage_accounting.total_tokens).toBe(110);
    expect(snapshot.usage_accounting.server_cache?.totals.hit_ratio).toBe(0);
  });
  it("excludes missing and contradictory fields from the reported hit-rate denominator",()=>{
    const usage=(id:string,hit:number)=>({model_request_id:id,provider:"fixture",model:"m",call_purpose:"review",usage:{input:100-hit,cache_read:hit,output:10}});
    let state=addServerCache(undefined,usage("1",0));
    expect(state.totals.hit_ratio).toBeNull();
    state=addServerCache(state,usage("2",0),{status:"reported",prompt_tokens:100,cache_read_tokens:0});
    state=addServerCache(state,usage("3",80),{status:"reported",prompt_tokens:100,cache_read_tokens:80});
    state=addServerCache(state,usage("4",0),{status:"inconsistent",prompt_tokens:100});
    expect(state.totals.hit_ratio).toBe(.4);
    expect(state.totals.unreported_responses).toBe(1);
    expect(state.totals.inconsistent_responses).toBe(1);
    expect(state.totals.reporting_coverage).toBe(.5);
  });
});
