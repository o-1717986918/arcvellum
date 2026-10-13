import { describe, expect, it } from "vitest";
import { applyCreativeEvent } from "./projection";
import type { CreativeLiveEvent, CreativeLiveSnapshot } from "./types";

function snapshot(): CreativeLiveSnapshot {
  return {
    ok: true,
    schema: "arcvellum/creative-live-snapshot/v1",
    project_id: "project",
    revision: "r1",
    status: "active",
    controller: null,
    active_task: { task_id: "scene-1" },
    artifacts: [],
    sessions: [],
    activity: [],
    reviews: [],
    usage: { total_tokens: 0, cost_usd: 0, updates: 0 },
    active_scene_transaction: null,
    scene_transactions: [],
    style_provenance: null,
    events: [],
    cursor: 0,
  };
}

function event(overrides: Partial<CreativeLiveEvent> = {}): CreativeLiveEvent {
  return {
    schema: "arcvellum/creative-live-event/v1",
    event_id: "event-1",
    sequence: 1,
    event: "artifact.preview.delta",
    channel: "artifact",
    visibility: "user",
    durability: "ephemeral",
    at: "2026-08-31T01:00:00Z",
    project_id: "project",
    run_id: "run-1",
    session_id: "session-1",
    task_id: "scene-1",
    route: "scene-development",
    attempt_id: "attempt-1",
    artifact: {
      artifact_id: "artifact-1",
      path: "drafts/scene_0001.md",
      kind: "prose",
      format: "markdown",
      identity: "streaming_preview",
      revision: 1,
      digest: "",
      characters: 2,
    },
    data: { delta: "开篇" },
    ...overrides,
  };
}

describe("Creative Live projection", () => {
  it("deduplicates usage after the display window drops the original event", () => {
    const usageEvent = event({ artifact:null,event:"usage.updated",channel:"usage",
      data:{ usage_id:"arcvellum-conversation-one-usage-1",invocation_id:"call",usage:{total_tokens:100,output:20,reasoning:15},cost_usd:0.1,
        price_estimate:{amount:0.2,currency:"CNY",source:"official",observed_at:"2026-10-11"} } });
    let current = applyCreativeEvent(snapshot(),usageEvent);
    for (let index=2; index<300; index++) current = applyCreativeEvent(current,
      event({ event_id:String(index),sequence:index,artifact:null,channel:"activity",event:"runner.session.status" }));
    current = applyCreativeEvent(current,{ ...usageEvent,event_id:"redelivered",sequence:300 });
    expect(current.usage.total_tokens).toBe(100);
    expect(current.usage_accounting?.public_estimate_cny).toBe(0.2);
    expect(current.usage_accounting?.token_details.output).toBe(20);
    expect(current.usage_accounting?.actual_charge).toBeNull();
  });

  it("counts logical calls and HTTP retries separately and preserves missing usage", () => {
    let current = snapshot();
    for (const [index,name,data] of [
      [1,"role.invocation.started",{invocation_id:"call"}],
      [2,"runner.provider.request.started",{model_request_id:"turn"}],
      [3,"runner.http.attempt.started",{http_attempt_id:"retry1"}],
      [4,"runner.http.attempt.started",{http_attempt_id:"retry2"}],
    ] as const) current = applyCreativeEvent(current,event({ event_id:String(index),sequence:index,event:name,data,artifact:null,channel:"activity" }));
    expect(current.usage_accounting).toMatchObject({outer_invocations:1,recorded_model_turns:1,
      observed_http_attempts:2,unknown_usage_invocations:1});
    current=applyCreativeEvent(current,event({ event_id:"missing",sequence:5,event:"usage.updated",channel:"usage",
      artifact:null,data:{ usage_id:"unknown",invocation_id:"call",usage_available:false,usage:{total_tokens:0},cost_usd:0 } }));
    expect(current.usage_accounting).toMatchObject({unknown_usage_updates:1,unknown_catalog_cost_updates:1,public_estimate_complete:false});
  });
  it("assembles prose deltas and advances candidate identity without duplicating events", () => {
    const first = applyCreativeEvent(snapshot(), event());
    const second = applyCreativeEvent(first, event({
      event_id: "event-2",
      sequence: 2,
      data: { delta: "继续" },
      artifact: { ...event().artifact!, characters: 4 },
    }));
    const promoted = applyCreativeEvent(second, event({
      event_id: "event-3",
      sequence: 3,
      event: "mutation.receipt",
      durability: "durable",
      artifact: { ...event().artifact!, identity: "promoted", characters: 4 },
      data: { title: "正文已晋升", message: "正式正文可阅读。" },
    }));

    expect(promoted.artifacts[0].content).toBe("开篇继续");
    expect(promoted.artifacts[0].identity).toBe("promoted");
    expect(applyCreativeEvent(promoted, promoted.events[0])).toBe(promoted);
  });

  it("does not replay an older preview over a reconnect snapshot", () => {
    const current = {
      ...snapshot(), live_cursor: 8,
      artifacts: [{
        ...event().artifact!, identity: "promoted" as const,
        content: "正式正文。", updated_at: event().at, source_event: "mutation.receipt",
      }],
    };
    expect(applyCreativeEvent(current, event({ sequence: 7 }))).toBe(current);
    expect(current.artifacts[0].identity).toBe("promoted");
  });

  it("collects visible transcript, tools and usage independently", () => {
    let value = applyCreativeEvent(snapshot(), event({
      event_id: "message",
      event: "agent.message.delta",
      channel: "transcript",
      artifact: null,
      data: { text: "我正在检查人物选择。" },
    }));
    value = applyCreativeEvent(value, event({
      event_id: "tool",
      sequence: 2,
      event: "tool.started",
      channel: "transcript",
      artifact: null,
      data: { tool: "read_task_source" },
    }));
    value = applyCreativeEvent(value, event({
      event_id: "usage",
      sequence: 3,
      event: "usage.updated",
      channel: "usage",
      artifact: null,
      data: { usage: { total_tokens: 900 }, cost_usd: 0.02 },
    }));

    expect(value.sessions[0].transcript).toContain("人物选择");
    expect(value.sessions[0].tools[0].tool).toBe("read_task_source");
    expect(value.usage).toEqual({ total_tokens: 900, cost_usd: 0.02, updates: 1 });
  });

  it("keeps a thirty-thousand-character prose stream readable while bounding event history", () => {
    const chunk = "潮声落在舷窗外。".repeat(75);
    let value = snapshot();
    for (let index = 1; index <= 50; index += 1) {
      value = applyCreativeEvent(value, event({
        event_id: `long-${index}`,
        sequence: index,
        data: { delta: chunk },
        artifact: { ...event().artifact!, characters: chunk.length * index },
      }));
    }

    expect(value.artifacts[0].content).toHaveLength(30_000);
    expect(value.artifacts[0].truncated).toBe(false);
    expect(value.events).toHaveLength(50);
    expect(value.cursor).toBe(50);
  });

  it("projects one lean scene transaction through its business states", () => {
    const prepared = applyCreativeEvent(snapshot(), event({
      event_id: "scene-prepared",
      event: "scene.prepared",
      channel: "activity",
      artifact: null,
      data: {
        scene_transaction_id: "scene-tx-1",
        scene_id: "scene_0001",
        status: "prepared",
        risk: "standard",
        objective: "主角决定进入封锁区",
        body_hanzi: 0,
      },
    }));
    const reviewed = applyCreativeEvent(prepared, event({
      event_id: "scene-reviewed",
      sequence: 2,
      event: "scene.reviewed",
      channel: "review",
      artifact: null,
      data: {
        scene_transaction_id: "scene-tx-1",
        scene_id: "scene_0001",
        status: "committable",
        review_decision: "pass",
        review_summary: "人物选择可信。",
        body_hanzi: 1680,
      },
    }));

    expect(reviewed.active_scene_transaction).toMatchObject({
      transaction_id: "scene-tx-1",
      status: "committable",
      body_hanzi: 1680,
      review_decision: "pass",
    });
    expect(reviewed.scene_transactions).toHaveLength(1);
  });
});
