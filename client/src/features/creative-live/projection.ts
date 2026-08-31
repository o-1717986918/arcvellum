import type {
  CreativeActivity,
  CreativeArtifact,
  CreativeLiveEvent,
  CreativeLiveSnapshot,
  CreativeSession,
} from "./types";

const MAX_ARTIFACT_CHARS = 2_000_000;
const MAX_TRANSCRIPT_CHARS = 120_000;

export function applyCreativeEvent(snapshot: CreativeLiveSnapshot, event: CreativeLiveEvent): CreativeLiveSnapshot {
  if (snapshot.events.some((item) => item.event_id === event.event_id)) return snapshot;
  const artifacts = reduceArtifact(snapshot.artifacts, event);
  const sessions = reduceSession(snapshot.sessions, event);
  const activity = event.channel === "activity" || event.channel === "control" || event.channel === "artifact" || event.channel === "review"
    ? [...snapshot.activity, activityFrom(event)].slice(-120)
    : snapshot.activity;
  const reviews = event.channel === "review"
    ? [...snapshot.reviews, reviewFrom(event)].slice(-120)
    : snapshot.reviews;
  const usage = event.channel === "usage" ? reduceUsage(snapshot.usage, event) : snapshot.usage;
  return {
    ...snapshot,
    status: event.event === "task.started" ? "active" : snapshot.status,
    artifacts,
    sessions,
    activity,
    reviews,
    usage,
    events: [...snapshot.events, event].slice(-240),
    cursor: Math.max(snapshot.cursor, Number(event.sequence || 0)),
  };
}

function reduceArtifact(items: CreativeArtifact[], event: CreativeLiveEvent): CreativeArtifact[] {
  if (!event.artifact) return items;
  const index = items.findIndex((item) => item.artifact_id === event.artifact?.artifact_id);
  const previous = index >= 0 ? items[index] : null;
  const content = typeof event.data.content === "string"
    ? event.data.content.slice(0, MAX_ARTIFACT_CHARS)
    : `${previous?.content || ""}${typeof event.data.delta === "string" ? event.data.delta : ""}`.slice(-MAX_ARTIFACT_CHARS);
  const next: CreativeArtifact = {
    ...(previous || { content: "", updated_at: "", source_event: "" }),
    ...event.artifact,
    content,
    updated_at: event.at,
    source_event: event.event,
    truncated: content.length >= MAX_ARTIFACT_CHARS,
  };
  const result = index >= 0 ? items.map((item, itemIndex) => itemIndex === index ? next : item) : [next, ...items];
  return result.sort((left, right) => String(right.updated_at).localeCompare(String(left.updated_at)));
}

function reduceSession(items: CreativeSession[], event: CreativeLiveEvent): CreativeSession[] {
  const sessionId = event.session_id || event.run_id;
  if (!sessionId) return items;
  const index = items.findIndex((item) => item.session_id === sessionId);
  const previous: CreativeSession = index >= 0 ? items[index] : {
    session_id: sessionId,
    role: "worker",
    runtime: "",
    status: "running",
    route: event.route,
    task_id: event.task_id,
    transcript: "",
    tools: [],
  };
  const transcript = event.event === "agent.message.delta"
    ? `${previous.transcript || ""}${String(event.data.text || "")}`.slice(-MAX_TRANSCRIPT_CHARS)
    : previous.transcript || "";
  const tools = event.event.startsWith("tool.")
    ? [...(previous.tools || []), { event: event.event, tool: String(event.data.tool || ""), status: String(event.data.status || ""), at: event.at }].slice(-40)
    : previous.tools || [];
  const next: CreativeSession = {
    ...previous,
    route: event.route || previous.route,
    task_id: event.task_id || previous.task_id,
    runtime: String(event.data.runtime || previous.runtime || ""),
    status: event.event === "runner.session.finished" ? String(event.data.status || "complete") : previous.status,
    transcript,
    tools,
    updated_at: event.at,
    last_event: event.event,
  };
  const result = index >= 0 ? items.map((item, itemIndex) => itemIndex === index ? next : item) : [next, ...items];
  return result.sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
}

function activityFrom(event: CreativeLiveEvent): CreativeActivity {
  return {
    event_id: event.event_id,
    event: event.event,
    channel: event.channel,
    at: event.at,
    task_id: event.task_id,
    route: event.route,
    title: String(event.data.title || "创作现场更新"),
    message: String(event.data.message || "项目状态已有新变化。"),
  };
}

function reviewFrom(event: CreativeLiveEvent) {
  return {
    ...activityFrom(event),
    status: String(event.data.status || ""),
    findings: Array.isArray(event.data.findings) ? event.data.findings : [],
    artifact_id: event.artifact?.artifact_id || "",
  };
}

function reduceUsage(current: CreativeLiveSnapshot["usage"], event: CreativeLiveEvent): CreativeLiveSnapshot["usage"] {
  const usage = typeof event.data.usage === "object" && event.data.usage ? event.data.usage as Record<string, unknown> : {};
  return {
    total_tokens: current.total_tokens + Number(usage.total_tokens || 0),
    cost_usd: current.cost_usd + Number(event.data.cost_usd || 0),
    updates: current.updates + 1,
  };
}

