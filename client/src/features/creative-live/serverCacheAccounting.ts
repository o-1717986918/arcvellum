import type { ServerCacheAccounting } from "./types";

export function addServerCache(previous: ServerCacheAccounting | undefined, data: Record<string, unknown>,
  raw?: Record<string, unknown>): ServerCacheAccounting {
  const usage = (data.usage || {}) as Record<string, unknown>;
  const value = (key:string) => Math.max(0,Number(usage[key]) || 0);
  let status = raw?.status || (value("cache_read") > 0 ? "legacy-positive" : "not-reported");
  const hit = raw?.cache_read_tokens ?? value("cache_read");
  if (status === "reported" && hit !== value("cache_read")) status = "inconsistent";
  const prompt = Number(raw?.prompt_tokens ?? (value("input")+value("cache_read")+value("cache_write")));
  const reported = status === "reported" || status === "legacy-positive";
  const binding = {
    provider:String(data.provider || ""), endpoint_sha256:String(raw?.endpoint_sha256 || ""),
    model:String(data.model || ""), call_purpose:String(data.call_purpose || data.role || ""),
    scene_transaction_id:String(data.scene_transaction_id || ""), request_series_id:String(raw?.request_series_id || ""),
  };
  const empty = { responses:0,reported_responses:0,unreported_responses:0,inconsistent_responses:0,
    total_input_tokens:0,reported_input_tokens:0,cache_read_tokens:0,output_tokens:0,hit_ratio:null,reporting_coverage:0 };
  const increment = (old:Record<string,number|null>) => {
    const next = { ...old };
    next.responses=Number(old.responses)+1;
    next.reported_responses=Number(old.reported_responses)+Number(reported);
    next.unreported_responses=Number(old.unreported_responses)+Number(status==="not-reported");
    next.inconsistent_responses=Number(old.inconsistent_responses)+Number(status==="inconsistent");
    next.total_input_tokens=Number(old.total_input_tokens)+prompt;
    next.reported_input_tokens=Number(old.reported_input_tokens)+(reported ? prompt : 0);
    next.cache_read_tokens=Number(old.cache_read_tokens)+(reported ? Number(hit) : 0);
    next.output_tokens=Number(old.output_tokens)+value("output");
    next.hit_ratio=next.reported_input_tokens ? next.cache_read_tokens/next.reported_input_tokens : null;
    next.reporting_coverage=next.reported_responses/next.responses;
    return next;
  };
  const groups = [...(previous?.groups || [])];
  const index=groups.findIndex(row=>Object.entries(binding).every(([key,val])=>row[key]===val));
  const prior=index<0 ? {...binding,...empty} : groups[index];
  const row={...prior,...increment(prior as Record<string,number|null>)};
  if(index<0) groups.push(row);else groups[index]=row;
  return {schema:"arcvellum/server-cache-accounting/v1",totals:increment(previous?.totals || empty),groups};
}
